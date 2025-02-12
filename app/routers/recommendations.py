from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import get_hybrid_recommendations
from app.models import Product
from app.schemas import ProductResponse

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/{user_id}", response_model=list[ProductResponse])
def get_recommendations(user_id: int, db: Session = Depends(get_db)):
    """
    Get top recommended products for a user using a hybrid approach with caching.
    """
    recommended_product_ids = get_hybrid_recommendations(user_id, db, limit=5)
    recommended_products = db.query(Product).filter(Product.product_id.in_(recommended_product_ids)).all()
    return recommended_products
