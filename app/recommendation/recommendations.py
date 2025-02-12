from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from .services import get_hybrid_recommendations, explain_recommendation
from app.database.models import Product
from .schemas import ProductResponse

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/{user_id}", response_model=list[ProductResponse])
def get_recommendations(user_id: int, db: Session = Depends(get_db)):
    """
    Get top recommended products for a user using a hybrid approach with caching.
    """
    recommended_product_ids = get_hybrid_recommendations(user_id, db, limit=5)
    recommended_products = db.query(Product).filter(Product.product_id.in_(recommended_product_ids)).all()
    return recommended_products

@router.get("/{user_id}/explain/{product_id}", response_model=str)
def get_recommendation_explanation(user_id: int, product_id: int, db: Session = Depends(get_db)):
    """
    Get an explanation for why a product was recommended.
    """
    explanation = explain_recommendation(user_id, product_id, db)
    return explanation
