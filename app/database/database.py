from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import redis
from ..config import REDIS_URL, POSTGRES_URL

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

engine = create_engine(POSTGRES_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency to get the database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
