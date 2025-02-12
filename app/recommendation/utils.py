from datetime import datetime
import json
from fastapi import HTTPException
from typing import Optional, List
from ..database.database import redis_client
from sqlalchemy.orm import Session
from ..database import models
from ..config import logger

CACHE_EXPIRATION = 3600
from datetime import datetime

async def explain_recommendation(user_id: Optional[int], product_id: int, db: Session) -> Optional[str]:
    try:
        logger.info(f"Explaining recommendation for user_id={user_id}, product_id={product_id}")
        user = db.query(models.User).filter_by(user_id=user_id).first() if user_id else None
        product = db.query(models.Product).filter_by(product_id=product_id).first()

        if not product or (user_id and not user):
            logger.info(f"No data found for user_id={user_id} or product_id={product_id}")
            return None

        explanation_parts = []

        if user_id:
            user_purchases = db.query(models.PurchaseHistory.product_id).filter_by(user_id=user_id).all()
            purchased_product_ids = [p.product_id for p in user_purchases]

            if product_id in purchased_product_ids:
                explanation_parts.append("Recommended because you have shown interest in similar products.")

            similar_users = (
                db.query(models.PurchaseHistory.user_id)
                .filter(models.PurchaseHistory.product_id.in_(purchased_product_ids))
                .distinct()
                .all()
            )

            similar_user_ids = [u.user_id for u in similar_users if u.user_id != user_id]

            similar_users_purchased = (
                db.query(models.PurchaseHistory.user_id)
                .filter(models.PurchaseHistory.user_id.in_(similar_user_ids), models.PurchaseHistory.product_id == product_id)
                .distinct()
                .all()
            )

            if similar_users_purchased:
                similar_users_names = [db.query(models.User.name).filter_by(user_id=u.user_id).first()[0] for u in similar_users_purchased]
                explanation_parts.append(f"Recommended because users similar to you ({', '.join(similar_users_names)}) purchased this.")

            browsing_history = db.query(models.BrowsingHistory.product_id).filter_by(user_id=user_id).all()
            viewed_product_ids = [b.product_id for b in browsing_history]

            if product_id in viewed_product_ids:
                explanation_parts.append("Recommended because you have viewed similar products.")

        current_day = datetime.utcnow().strftime('%A')
        current_season = get_current_season()

        contextual_signals = db.query(models.ContextualSignal).all()
        relevant_signals = [
            signal for signal in contextual_signals
            if current_day in signal.peak_days.split(',') or signal.season == current_season
        ]

        if relevant_signals:
            relevant_categories = [signal.category for signal in relevant_signals]
            if product.category in relevant_categories:
                explanation_parts.append(f"Recommended based on current trends: {current_day} and {current_season}.")

        if not explanation_parts:
            explanation_parts.append("Recommended based on trending and popular products.")

        logger.info(f"Explanation for user_id={user_id}, product_id={product_id}: {explanation_parts}")
        return " ".join(explanation_parts)
    except Exception as e:
        logger.error(f"Error explaining recommendation for user_id={user_id}, product_id={product_id}: {e}")
        raise HTTPException(status_code=500, detail="Error explaining recommendation")

def get_current_season() -> str:
    """
    Determine the current season or special event based on the current date.
    """
    month = datetime.utcnow().month
    day = datetime.utcnow().day

    # Check for specific holidays and events
    if (month == 12 and day >= 24) or (month == 12 and day <= 26):
        return "Christmas"
    if (month == 11 and day >= 22 and day <= 28) and datetime.utcnow().strftime('%A') == "Thursday":
        return "Thanksgiving"
    if (month == 10 and day == 31):
        return "Halloween"
    if (month == 2 and day == 14):
        return "Valentine's Day"

    # Determine the season
    if (month == 12 and day >= 21) or (month in [1, 2]) or (month == 3 and day < 20):
        return "Winter"
    elif (month == 3 and day >= 20) or (month in [4, 5]) or (month == 6 and day < 21):
        return "Spring"
    elif (month == 6 and day >= 21) or (month in [7, 8]) or (month == 9 and day < 22):
        return "Summer"
    elif (month == 9 and day >= 22) or (month in [10, 11]) or (month == 12 and day < 21):
        return "Fall"
    
    return "Unknown"

async def cache_recommendations(user_id: int, recommendations: List[int]) -> None:
    redis_client.setex(f"recommendations:{user_id}", CACHE_EXPIRATION, json.dumps(recommendations))

async def get_cached_recommendations(user_id: int) -> Optional[List[int]]:
    cached_data = redis_client.get(f"recommendations:{user_id}")
    return json.loads(cached_data) if cached_data else None
