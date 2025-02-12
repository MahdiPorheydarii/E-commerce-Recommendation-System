from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/recommendations")

# Database setup
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency to get the database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(
    title="Recommendation System API", 
    version="1.0", 
    description="An advanced recommendation system for an e-commerce platform."
)

@app.get("/", summary="Root Endpoint", tags=["Health Check"])
def read_root():
    """Root endpoint to check API status."""
    return {"message": "Welcome to the Recommendation System API"}
