from fastapi import FastAPI
from database import models, database
from config import logger
from recommendation.recommendations import router as recommendations_router

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Recommendation System API", 
    version="1.0"
)

@app.get("/", summary="Root Endpoint", tags=["Health Check"])
def read_root():
    return {"message": "Hello"}

app.include_router(recommendations_router)