from fastapi import FastAPI
from database import models, database

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Recommendation System API", 
    version="1.0"
    )

@app.get("/", summary="Root Endpoint", tags=["Health Check"])
def read_root():
    """Root endpoint to check API status."""
    return {"message": "Welcome to the Recommendation System API"}
