from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from ..database import models
from datetime import datetime, timedelta
from ..config import logger
from scipy.sparse.linalg import svds
import scipy.sparse as sp
import pandas as pd
import numpy as np
from .utils import get_current_season, cache_recommendations, get_cached_recommendations
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional
import asyncio

async def get_hybrid_recommendations(user_id: Optional[int], db: Session, limit: int = 10) -> List[int]:
    try:
        logger.info(f"Fetching recommendations for user_id={user_id}")

        if user_id is not None:
            cached_recommendations = await get_cached_recommendations(user_id)
            if cached_recommendations:
                return cached_recommendations
        else:
            return await get_trending_products(db, user_id, limit)

        user_exists = db.query(models.User).filter_by(user_id=user_id).first()
        if not user_exists:
            raise HTTPException(status_code=404, detail=f"User with user_id={user_id} not found")

        browsing_history = db.query(models.BrowsingHistory).filter_by(user_id=user_id).first()
        purchase_history = db.query(models.PurchaseHistory).filter_by(user_id=user_id).first()

        if not browsing_history and not purchase_history:
            logger.info(f"No browsing or purchase history for user_id={user_id}, falling back to trending products")
            return await get_trending_products(db, user_id, limit)

        collaborative, content_based, personalized, contextual, svd = await asyncio.gather(
            get_user_based_recommendations(user_id, db, limit),
            get_content_based_recommendations(user_id, db, limit),
            get_personalized_recommendations(user_id, db, limit),
            get_contextual_recommendations(user_id, db, limit),
            get_svd_recommendations(user_id, db, limit)
        )

        combined_recommendations = list(set(collaborative + content_based + personalized + contextual + svd))

        if len(combined_recommendations) < limit:
            trending = await get_trending_products(db, user_id, limit)
            combined_recommendations += trending

        final_recommendations = await enforce_diversity(combined_recommendations, db, limit)
        
        await cache_recommendations(user_id, final_recommendations)
        logger.info(f"Final recommendations for user_id={user_id}: {final_recommendations}")
        
        return final_recommendations
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching hybrid recommendations for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching hybrid recommendations")

async def get_interacted_product_ids(user_id: Optional[int], db: Session) -> set:
    try:
        if user_id is None:
            return set()
        logger.info(f"Fetching interacted product IDs for user_id={user_id}")
        user_interactions = db.query(models.PurchaseHistory.product_id).filter_by(user_id=user_id).all()
        user_interactions += db.query(models.BrowsingHistory.product_id).filter_by(user_id=user_id).all()
        user_interactions += db.query(models.UserInteraction.product_id).filter_by(user_id=user_id).all()
        interacted_product_ids = {p.product_id for p in user_interactions}
        logger.info(f"Interacted product IDs for user_id={user_id}: {interacted_product_ids}")
        return interacted_product_ids
    except Exception as e:
        logger.error(f"Error fetching interacted product IDs for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching interacted product IDs")

async def get_trending_products(db: Session, user_id: Optional[int], limit: int = 5) -> List[int]:
    try:
        logger.info(f"Fetching trending products for user_id={user_id}")
        one_month_ago = datetime.utcnow() - timedelta(days=30)
        interacted_product_ids = await get_interacted_product_ids(user_id, db)


        trending = (
            db.query(models.PurchaseHistory.product_id, func.count(models.PurchaseHistory.product_id).label("purchase_count"))
            .filter(models.PurchaseHistory.timestamp >= one_month_ago)
            .filter(~models.PurchaseHistory.product_id.in_(list(interacted_product_ids)))  # Ensure list conversion for PostgreSQL
            .group_by(models.PurchaseHistory.product_id)
            .order_by(func.count(models.PurchaseHistory.product_id).desc())
            .limit(limit)
            .all()
        )

        trending_product_ids = [p.product_id for p in trending]
        logger.info(f"Trending products for user_id={user_id}: {trending_product_ids}")
        return trending_product_ids
    except Exception as e:
        logger.error(f"Error fetching trending products for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching trending products")

async def get_user_based_recommendations(user_id: Optional[int], db: Session, limit: int = 5) -> List[int]:
    try:
        logger.info(f"Fetching user-based recommendations for user_id={user_id}")
        user_purchases = db.query(models.PurchaseHistory).filter_by(user_id=user_id).all()
        purchased_product_ids = [p.product_id for p in user_purchases]

        if not purchased_product_ids:
            logger.info(f"No purchase history for user_id={user_id}, falling back to trending products")
            return await get_trending_products(db, user_id, limit)  # Cold start fallback

        interactions = db.query(models.PurchaseHistory).all()
        data = {
            'user_id': [i.user_id for i in interactions],
            'product_id': [i.product_id for i in interactions],
            'quantity': [i.quantity for i in interactions]
        }
        df = pd.DataFrame(data)
        user_product_matrix = df.pivot_table(index='user_id', columns='product_id', values='quantity', fill_value=0)

        user_similarity = cosine_similarity(user_product_matrix)
        user_similarity_df = pd.DataFrame(user_similarity, index=user_product_matrix.index, columns=user_product_matrix.index)

        similar_users = user_similarity_df[user_id].sort_values(ascending=False).index[1:limit+1]
        similar_users_purchases = df[df['user_id'].isin(similar_users)]
        recommended_products = similar_users_purchases['product_id'].value_counts().index.tolist()

        logger.info(f"User-based recommendations for user_id={user_id}: {recommended_products[:limit]}")
        return recommended_products[:limit]
    except Exception as e:
        logger.error(f"Error fetching user-based recommendations for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user-based recommendations")

async def get_content_based_recommendations(user_id: Optional[int], db: Session, limit: int = 5) -> List[int]:
    try:
        logger.info(f"Fetching content-based recommendations for user_id={user_id}")
        browsing_history = db.query(models.BrowsingHistory).filter_by(user_id=user_id).all()
        viewed_product_ids = [b.product_id for b in browsing_history]

        if not viewed_product_ids:
            logger.info(f"No browsing history for user_id={user_id}, falling back to trending products")
            return await get_trending_products(db, user_id, limit)  # Cold start fallback

        products = db.query(models.Product).all()
        data = {
            'product_id': [p.product_id for p in products],
            'category': [p.category for p in products],
            'tags': [p.tags for p in products],
            'rating': [p.rating for p in products]
        }
        df = pd.DataFrame(data)
        df['tags'] = df['tags'].fillna('').apply(lambda x: ' '.join(x))
        df['features'] = df['category'] + ' ' + df['tags']

        product_features_matrix = df.pivot_table(index='product_id', values='rating', fill_value=0)
        product_similarity = cosine_similarity(product_features_matrix)
        product_similarity_df = pd.DataFrame(product_similarity, index=product_features_matrix.index, columns=product_features_matrix.index)

        if not viewed_product_ids:
            logger.info(f"No browsing history for user_id={user_id}, falling back to trending products")
            return await get_trending_products(db, user_id, limit)  # Cold start fallback

        # Ensure viewed_product_ids exist in product_similarity_df index
        valid_product_ids = [pid for pid in viewed_product_ids if pid in product_similarity_df.index]

        if not valid_product_ids:  
            logger.info(f"Viewed products not found in dataset for user_id={user_id}, returning trending products")
            return await get_trending_products(db, user_id, limit)

        similar_products = product_similarity_df.loc[valid_product_ids].mean().sort_values(ascending=False).index.tolist()


        logger.info(f"Content-based recommendations for user_id={user_id}: {similar_products[:limit]}")
        return similar_products[:limit]
    except Exception as e:
        logger.error(f"Error fetching content-based recommendations for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching content-based recommendations")

async def get_personalized_recommendations(user_id: Optional[int], db: Session, limit: int = 5) -> List[int]:
    try:
        logger.info(f"Fetching personalized recommendations for user_id={user_id}")
        user = db.query(models.User).filter_by(user_id=user_id).first()

        current_hour = datetime.utcnow().hour
        device_type = user.device

        personalized_products = (
            db.query(models.Product.product_id)
            .filter(models.Product.meta.contains(f'"device_type": "{device_type}"'))
            .limit(limit * 2)  # Increase limit in case filtering reduces options
            .all()
        )

        if not personalized_products:
            logger.info(f"No personalized matches for user_id={user_id}, returning trending products")
            return await get_trending_products(db, user_id, limit)

        return [p.product_id for p in personalized_products[:limit]]

    except Exception as e:
        logger.error(f"Error fetching personalized recommendations for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching personalized recommendations")

async def get_contextual_recommendations(user_id: Optional[int], db: Session, limit: int = 5) -> List[int]:
    try:
        logger.info(f"Fetching contextual recommendations for user_id={user_id}")
        user = db.query(models.User).filter_by(user_id=user_id).first()

        current_day = datetime.utcnow().strftime('%A')
        current_season = get_current_season()

        contextual_signals = db.query(models.ContextualSignal).all()
        relevant_signals = [
            signal for signal in contextual_signals
            if current_day in signal.peak_days.split(',') or signal.season == current_season
        ]

        if not relevant_signals:
            logger.info(f"No relevant contextual signals for user_id={user_id}, falling back to trending products")
            return await get_trending_products(db, user_id, limit)  # Fallback if no relevant signals

        relevant_categories = [signal.category for signal in relevant_signals]
        contextual_products = (
            db.query(models.Product.product_id)
            .filter(models.Product.category.in_(relevant_categories))
            .limit(limit)
            .all()
        )

        contextual_product_ids = [p.product_id for p in contextual_products]
        logger.info(f"Contextual recommendations for user_id={user_id}: {contextual_product_ids}")
        return contextual_product_ids
    except Exception as e:
        logger.error(f"Error fetching contextual recommendations for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching contextual recommendations")

async def get_svd_recommendations(user_id: Optional[int], db: Session, limit: int = 5) -> List[int]:
    """
    Uses Singular Value Decomposition (SVD) for collaborative filtering without external libraries.
    """
    try:
        logger.info(f"Computing SVD recommendations for user_id={user_id}")

        interactions = db.query(models.PurchaseHistory).all()

        data = {
            "user_id": [i.user_id for i in interactions],
            "product_id": [i.product_id for i in interactions],
            "rating": [i.quantity for i in interactions]  # Using quantity as implicit feedback
        }

        df = pd.DataFrame(data)

        if df.empty or (user_id is not None and user_id not in df["user_id"].values):
            logger.warning(f"No interactions found for user_id={user_id}, falling back to trending products")
            return await get_trending_products(db, user_id, limit)  # Cold start fallback

        # Convert to sparse matrix
        unique_users = df["user_id"].unique()
        unique_products = df["product_id"].unique()

        user_map = {u: i for i, u in enumerate(unique_users)}
        product_map = {p: i for i, p in enumerate(unique_products)}

        user_inv_map = {i: u for u, i in user_map.items()}
        product_inv_map = {i: p for p, i in product_map.items()}

        rows = df["user_id"].map(user_map)
        cols = df["product_id"].map(product_map)
        values = df["rating"].astype(float)

        sparse_matrix = sp.csr_matrix((values, (rows, cols)), shape=(len(unique_users), len(unique_products)))

        # Apply SVD (Singular Value Decomposition)
        U, sigma, Vt = svds(sparse_matrix, k=min(10, min(sparse_matrix.shape) - 1))
        sigma = np.diag(sigma)

        if user_id not in user_map:
            logger.warning(f"user_id={user_id} not found in training data, falling back to trending products")
            return await get_trending_products(db, user_id, limit)

        user_idx = user_map[user_id]
        user_ratings = np.dot(np.dot(U[user_idx, :], sigma), Vt)

        # Convert to a NumPy array and replace NaN with 0
        user_ratings = np.nan_to_num(user_ratings)

        recommended_idx = np.argsort(-user_ratings)[:limit]

        # Ensure recommended indexes exist in the product map
        recommended_product_ids = [
            int(product_inv_map[i]) for i in recommended_idx if i in product_inv_map and isinstance(product_inv_map[i], int)
        ]
        if not recommended_product_ids:
            logger.warning(f"SVD produced empty recommendations for user_id={user_id}, falling back to trending products")
            return await get_trending_products(db, user_id, limit)

        return recommended_product_ids

    except Exception as e:
        logger.error(f"Error computing SVD recommendations for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error computing SVD recommendations")

async def enforce_diversity(recommendations: List[int], db: Session, limit: int) -> List[int]:
    """
    Ensures recommendations are diverse by including products from different categories.
    """
    try:
        product_details = db.query(models.Product).filter(models.Product.product_id.in_(recommendations)).all()
        category_map = {}
        final_recommendations = []

        for product in product_details:
            if product.category not in category_map:
                category_map[product.category] = []
            category_map[product.category].append(product.product_id)

        while len(final_recommendations) < limit:
            for category, products in category_map.items():
                if products:
                    final_recommendations.append(products.pop(0))
                if len(final_recommendations) >= limit:
                    break

        logger.info(f"Final diversified recommendations: {final_recommendations}")
        return final_recommendations
    except Exception as e:
        logger.error(f"Error enforcing diversity in recommendations: {e}")
        raise HTTPException(status_code=500, detail="Error enforcing diversity in recommendations")
