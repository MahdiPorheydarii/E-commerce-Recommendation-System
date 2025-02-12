from sqlalchemy.orm import Session
from collections import Counter
from app import models
from app.database import redis_client
import json

def get_trending_products(db: Session, limit: int = 5):
    """
    Fetches trending products based on most purchased items.
    """
    trending = (
        db.query(models.PurchaseHistory.product_id)
        .group_by(models.PurchaseHistory.product_id)
        .order_by(models.PurchaseHistory.product_id.count().desc())
        .limit(limit)
        .all()
    )
    return [p.product_id for p in trending]

def get_user_based_recommendations(user_id: int, db: Session, limit: int = 5):
    """
    Collaborative filtering: Recommend products based on similar users' interactions.
    """
    user_purchases = db.query(models.PurchaseHistory.product_id).filter_by(user_id=user_id).all()
    purchased_product_ids = [p.product_id for p in user_purchases]

    if not purchased_product_ids:
        return get_trending_products(db, limit)  # Cold start fallback

    similar_users = (
        db.query(models.PurchaseHistory.user_id)
        .filter(models.PurchaseHistory.product_id.in_(purchased_product_ids))
        .distinct()
        .all()
    )

    similar_user_ids = [u.user_id for u in similar_users if u.user_id != user_id]

    recommended_products = (
        db.query(models.PurchaseHistory.product_id)
        .filter(models.PurchaseHistory.user_id.in_(similar_user_ids))
        .group_by(models.PurchaseHistory.product_id)
        .order_by(models.PurchaseHistory.product_id.count().desc())
        .limit(limit)
        .all()
    )

    return [p.product_id for p in recommended_products]

def get_content_based_recommendations(user_id: int, db: Session, limit: int = 5):
    """
    Content-based filtering: Recommend products similar to ones the user has viewed.
    """
    browsing_history = db.query(models.BrowsingHistory.product_id).filter_by(user_id=user_id).all()
    viewed_product_ids = [b.product_id for b in browsing_history]

    if not viewed_product_ids:
        return get_trending_products(db, limit)  # Cold start fallback

    category_counts = Counter(
        db.query(models.Product.category)
        .filter(models.Product.product_id.in_(viewed_product_ids))
        .all()
    )

    most_common_category = category_counts.most_common(1)[0][0]

    recommended_products = (
        db.query(models.Product.product_id)
        .filter(models.Product.category == most_common_category)
        .limit(limit)
        .all()
    )

    return [p.product_id for p in recommended_products]

CACHE_EXPIRATION = 3600  # Cache recommendations for 1 hour

def cache_recommendations(user_id: int, recommendations: list[int]):
    """
    Store recommendations in Redis with an expiration time.
    """
    redis_client.setex(f"recommendations:{user_id}", CACHE_EXPIRATION, json.dumps(recommendations))

def get_cached_recommendations(user_id: int):
    """
    Retrieve cached recommendations if available.
    """
    cached_data = redis_client.get(f"recommendations:{user_id}")
    return json.loads(cached_data) if cached_data else None

def get_hybrid_recommendations(user_id: int, db: Session, limit: int = 5):
    """
    Combines multiple recommendation strategies with caching.
    """
    cached_recommendations = get_cached_recommendations(user_id)
    if cached_recommendations:
        return cached_recommendations

    collaborative = get_user_based_recommendations(user_id, db, limit)
    content_based = get_content_based_recommendations(user_id, db, limit)

    final_recommendations = list(set(collaborative + content_based))[:limit]
    if not final_recommendations:
        final_recommendations = get_trending_products(db, limit)

    cache_recommendations(user_id, final_recommendations)
    return final_recommendations
