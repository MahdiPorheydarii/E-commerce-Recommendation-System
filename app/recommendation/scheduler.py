from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
import asyncio
import logging
from .services import get_hybrid_recommendations
from .utils import cache_recommendations
from app.database import models
from app.database.database import SessionLocal
from main import logger

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
        asyncio.run(cache_recommendations(user_id, recommendations))

    logger.info("Batch recommendation computation complete.")

scheduler.add_job(precompute_recommendations, 'interval', hours=6, args=[SessionLocal()])
scheduler.start()