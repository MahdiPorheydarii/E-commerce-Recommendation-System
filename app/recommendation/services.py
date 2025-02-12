from sqlalchemy.orm import Session
from collections import Counter
from app import models
from app.database import redis_client
from datetime import datetime
import json
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional

CACHE_EXPIRATION = 3600

def get_trending_products(db: Session, limit: int = 5) -> List[int]:
    trending = (
        db.query(models.PurchaseHistory.product_id)
        .group_by(models.PurchaseHistory.product_id)
        .order_by(models.PurchaseHistory.product_id.count().desc())
        .limit(limit)
        .all()
    )
    return [p.product_id for p in trending]

def get_user_based_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    user_purchases = db.query(models.PurchaseHistory).filter_by(user_id=user_id).all()
    purchased_product_ids = [p.product_id for p in user_purchases]

    if not purchased_product_ids:
        return get_trending_products(db, limit)  # Cold start fallback

    # Create user-product interaction matrix
    interactions = db.query(models.PurchaseHistory).all()
    data = {
        'user_id': [i.user_id for i in interactions],
        'product_id': [i.product_id for i in interactions],
        'quantity': [i.quantity for i in interactions]
    }
    df = pd.DataFrame(data)
    user_product_matrix = df.pivot_table(index='user_id', columns='product_id', values='quantity', fill_value=0)

    # Compute similarity matrix
    user_similarity = cosine_similarity(user_product_matrix)
    user_similarity_df = pd.DataFrame(user_similarity, index=user_product_matrix.index, columns=user_product_matrix.index)

    # Get similar users
    similar_users = user_similarity_df[user_id].sort_values(ascending=False).index[1:limit+1]

    # Get products purchased by similar users
    similar_users_purchases = df[df['user_id'].isin(similar_users)]
    recommended_products = similar_users_purchases['product_id'].value_counts().index.tolist()

    return recommended_products[:limit]

def get_content_based_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    browsing_history = db.query(models.BrowsingHistory).filter_by(user_id=user_id).all()
    viewed_product_ids = [b.product_id for b in browsing_history]

    if not viewed_product_ids:
        return get_trending_products(db, limit)  # Cold start fallback

    # Create product feature matrix
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

    # Compute similarity matrix
    product_features_matrix = df.pivot_table(index='product_id', values='rating', fill_value=0)
    product_similarity = cosine_similarity(product_features_matrix)
    product_similarity_df = pd.DataFrame(product_similarity, index=product_features_matrix.index, columns=product_features_matrix.index)

    # Get similar products
    similar_products = product_similarity_df.loc[viewed_product_ids].mean().sort_values(ascending=False).index.tolist()

    return similar_products[:limit]

def get_personalized_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    user = db.query(models.User).filter_by(user_id=user_id).first()
    if not user:
        return get_trending_products(db, limit)  # Cold start fallback

    # Example: Recommend products based on time of day and device type
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

def get_hybrid_recommendations(user_id: int, db: Session, limit: int = 5) -> List[int]:
    cached_recommendations = get_cached_recommendations(user_id)
    if cached_recommendations:
        return cached_recommendations

    collaborative = get_user_based_recommendations(user_id, db, limit)
    content_based = get_content_based_recommendations(user_id, db, limit)
    personalized = get_personalized_recommendations(user_id, db, limit)

    final_recommendations = list(set(collaborative + content_based + personalized))[:limit]
    if not final_recommendations:
        final_recommendations = get_trending_products(db, limit)

    cache_recommendations(user_id, final_recommendations)
    return final_recommendations

def cache_recommendations(user_id: int, recommendations: List[int]) -> None:
    redis_client.setex(f"recommendations:{user_id}", CACHE_EXPIRATION, json.dumps(recommendations))

def get_cached_recommendations(user_id: int) -> Optional[List[int]]:
    cached_data = redis_client.get(f"recommendations:{user_id}")
    return json.loads(cached_data) if cached_data else None

def explain_recommendation(user_id: int, product_id: int, db: Session) -> Optional[str]:
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

    return "Recommended based on trending and popular products."
