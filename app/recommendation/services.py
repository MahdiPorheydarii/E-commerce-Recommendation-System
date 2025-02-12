from sqlalchemy.orm import Session
from app.database import models
from app.database.database import SessionLocal
from datetime import datetime, timedelta
from main import logger
import pandas as pd
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import svds
import scipy.sparse as sp
from utils import get_current_season, cache_recommendations, get_cached_recommendations
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional
import asyncio


async def get_hybrid_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    """
    Get hybrid recommendations while ensuring diversity across product categories.
    """
    logger.info(f"Fetching recommendations for user_id={user_id}")

    cached_recommendations = await get_cached_recommendations(user_id)
    if cached_recommendations:
        logger.info(f"Cache hit for user_id={user_id}")
        return cached_recommendations

    collaborative, content_based, personalized, contextual, svd = await asyncio.gather(
        get_user_based_recommendations(user_id, db, limit),
        get_content_based_recommendations(user_id, db, limit),
        get_personalized_recommendations(user_id, db, limit),
        get_contextual_recommendations(user_id, db, limit),
        get_svd_recommendations(user_id, db, limit)  # Now using SVD instead of ALS
    )

    combined_recommendations = list(set(collaborative + content_based + personalized + contextual + svd))

    if len(combined_recommendations) < limit:
        trending = await get_trending_products(db, user_id, limit)
        combined_recommendations += trending

    final_recommendations = await enforce_diversity(combined_recommendations, db, limit)
    
    await cache_recommendations(user_id, final_recommendations)
    logger.info(f"Final recommendations for user_id={user_id}: {final_recommendations}")
    
    return final_recommendations

async def get_interacted_product_ids(user_id: int, db: Session) -> set:
    """
    Get the set of product IDs the user has interacted with.
    """
    user_interactions = db.query(models.PurchaseHistory.product_id).filter_by(user_id=user_id).all()
    user_interactions += db.query(models.BrowsingHistory.product_id).filter_by(user_id=user_id).all()
    user_interactions += db.query(models.UserInteraction.product_id).filter_by(user_id=user_id).all()
    return {p.product_id for p in user_interactions}

async def get_trending_products(db: Session, user_id: int, limit: int = 5) -> List[int]:
    """
    Fetches trending products based on the most purchased items in the last month, excluding products the user has interacted with.
    """
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    interacted_product_ids = await get_interacted_product_ids(user_id, db)

    trending = (
        db.query(models.PurchaseHistory.product_id)
        .filter(models.PurchaseHistory.timestamp >= one_month_ago)
        .filter(~models.PurchaseHistory.product_id.in_(interacted_product_ids))
        .group_by(models.PurchaseHistory.product_id)
        .order_by(models.PurchaseHistory.product_id.count().desc())
        .limit(limit)
        .all()
    )
    return [p.product_id for p in trending]

async def get_user_based_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    """
    Get user-based collaborative filtering recommendations.
    """
    user_purchases = db.query(models.PurchaseHistory).filter_by(user_id=user_id).all()
    purchased_product_ids = [p.product_id for p in user_purchases]

    if not purchased_product_ids:
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

    return recommended_products[:limit]

async def get_content_based_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    """
    Get content-based filtering recommendations.
    """
    browsing_history = db.query(models.BrowsingHistory).filter_by(user_id=user_id).all()
    viewed_product_ids = [b.product_id for b in browsing_history]

    if not viewed_product_ids:
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

    similar_products = product_similarity_df.loc[viewed_product_ids].mean().sort_values(ascending=False).index.tolist()

    return similar_products[:limit]

async def get_personalized_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    """
    Get personalized recommendations based on user-specific data.
    """
    user = db.query(models.User).filter_by(user_id=user_id).first()
    if not user:
        return await get_trending_products(db, user_id, limit)  # Cold start fallback

    current_hour = datetime.utcnow().hour
    device_type = user.device

    personalized_products = (
        db.query(models.Product.product_id)
        .filter(models.Product.metadata.contains(f'"device_type": "{device_type}"'))
        .filter(models.Product.metadata.contains(f'"active_hours": "{current_hour}"'))
        .limit(limit)
        .all()
    )

    return [p.product_id for p in personalized_products]

async def get_contextual_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    """
    Get recommendations based on contextual signals, now including time of day and device type.
    """
    user = db.query(models.User).filter_by(user_id=user_id).first()
    if not user:
        return await get_trending_products(db, user_id, limit)  # Cold start fallback

    current_day = datetime.utcnow().strftime('%A')
    current_hour = datetime.utcnow().hour
    time_of_day = (
        "Morning" if 5 <= current_hour < 12 else
        "Afternoon" if 12 <= current_hour < 17 else
        "Evening" if 17 <= current_hour < 21 else
        "Night"
    )

    contextual_signals = db.query(models.ContextualSignal).all()
    relevant_signals = [
        signal for signal in contextual_signals
        if (current_day in signal.peak_days.split(',') or signal.season == get_current_season()) and
           (signal.time_of_day is None or signal.time_of_day == time_of_day) and
           (signal.device_type is None or signal.device_type == user.device)
    ]

    if not relevant_signals:
        return await get_trending_products(db, user_id, limit)  # Fallback if no relevant signals

    relevant_categories = [signal.category for signal in relevant_signals]
    contextual_products = (
        db.query(models.Product.product_id)
        .filter(models.Product.category.in_(relevant_categories))
        .limit(limit)
        .all()
    )

    return [p.product_id for p in contextual_products]

async def explain_recommendation(user_id: int, product_id: int, db: Session) -> Optional[str]:
    """
    Provide an explanation for why a product was recommended.
    """
    user = db.query(models.User).filter_by(user_id=user_id).first()
    product = db.query(models.Product).filter_by(product_id=product_id).first()

    if not product or not user:
        return None

    user_purchases = db.query(models.PurchaseHistory.product_id).filter_by(user_id=user_id).all()
    purchased_product_ids = [p.product_id for p in user_purchases]

    if product_id in purchased_product_ids:
        return "Recommended because you have shown interest in similar products."

    similar_users = (
        db.query(models.PurchaseHistory.user_id)
        .filter(models.PurchaseHistory.product_id.in_(purchased_product_ids))
        .distinct()
        .all()
    )

    similar_user_ids = [u.user_id for u in similar_users if u.user_id != user_id]

    if db.query(models.PurchaseHistory).filter(models.PurchaseHistory.user_id.in_(similar_user_ids), models.PurchaseHistory.product_id == product_id).count() > 0:
        return "Recommended because users similar to you purchased this."

    browsing_history = db.query(models.BrowsingHistory.product_id).filter_by(user_id=user_id).all()
    viewed_product_ids = [b.product_id for b in browsing_history]

    if product_id in viewed_product_ids:
        return "Recommended because you have viewed similar products."

    return "Recommended based on trending and popular products."

async def get_svd_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    """
    Uses Singular Value Decomposition (SVD) for collaborative filtering without external libraries.
    """
    logger.info(f"Computing SVD recommendations for user_id={user_id}")

    interactions = db.query(models.PurchaseHistory).all()

    data = {
        "user_id": [i.user_id for i in interactions],
        "product_id": [i.product_id for i in interactions],
        "rating": [i.quantity for i in interactions]  # Using quantity as implicit feedback
    }

    df = pd.DataFrame(data)

    if df.empty or user_id not in df["user_id"].values:
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
    U, sigma, Vt = svds(sparse_matrix, k=min(50, min(sparse_matrix.shape) - 1))
    sigma = np.diag(sigma)

    # Compute user recommendations
    user_idx = user_map.get(user_id)
    if user_idx is None:
        logger.warning(f"user_id={user_id} not found in SVD model, falling back to trending products")
        return await get_trending_products(db, user_id, limit)  # Cold start fallback

    user_ratings = np.dot(np.dot(U[user_idx, :], sigma), Vt)
    recommended_idx = np.argsort(-user_ratings)[:limit]  # Sort and take top N

    recommended_product_ids = [product_inv_map[i] for i in recommended_idx if i in product_inv_map]

    logger.info(f"SVD recommendations for user_id={user_id}: {recommended_product_ids}")
    return recommended_product_ids

async def enforce_diversity(recommendations: List[int], db: Session, limit: int) -> List[int]:
    """
    Ensures recommendations are diverse by including products from different categories.
    """
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

scheduler = BackgroundScheduler()

def precompute_recommendations(db: Session):
    """
    Runs a batch job to precompute recommendations for all active users.
    """
    logger.info("Starting batch recommendation computation...")
    
    users = db.query(models.User.user_id).all()
    user_ids = [u.user_id for u in users]

    for user_id in user_ids:
        recommendations = asyncio.run(get_hybrid_recommendations(user_id, db, limit=10))
        cache_recommendations(user_id, recommendations)

    logger.info("Batch recommendation computation complete.")

scheduler.add_job(precompute_recommendations, 'interval', hours=6, args=[SessionLocal()])
scheduler.start()
