from fastapi import FastAPI
from .database import models, database
from .config import logger
from .recommendation.recommendations import router as recommendations_router
from dotenv import load_dotenv
import logfire

load_dotenv()

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Recommendation System API", 
    version="1.0"
)

logfire.configure()
logfire.instrument_fastapi(app)

@app.get("/", summary="Root Endpoint", tags=["Health Check"])
def read_root():
    return {"message": "Hello"}

app.include_router(recommendations_router)