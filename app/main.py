from fastapi import FastAPI
from database import models, database
import logging
from recommendation.scheduler import scheduler  # Import the scheduler to initialize it

models.Base.metadata.create_all(bind=database.engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Recommendation System API", 
    version="1.0"
)

@app.get("/", summary="Root Endpoint", tags=["Health Check"])
def read_root():
    """Root endpoint to check API status."""
    return {"message": "Welcome to the Recommendation System API"}

scheduler.start()