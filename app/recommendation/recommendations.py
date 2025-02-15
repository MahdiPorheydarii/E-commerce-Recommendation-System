from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import database, models
from .services import get_hybrid_recommendations
from .utils import explain_recommendation
from ..database.models import Product
from .schemas import ProductResponse
from typing import List, Optional

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/{user_id}", response_model=List[ProductResponse], summary="Get Recommendations",
            description="Get top recommended products for a user using a hybrid approach with caching.",
            responses={200: {"description": "Successful Response"},
                       404: {"description": "User not found or no recommendations available"}
                       }
            )
async def get_recommendations(user_id: Optional[int] = None, db: Session = Depends(database.get_db)):
    """
    Get top recommended products for a user using a hybrid approach with caching.
    """
    recommended_product_ids = await get_hybrid_recommendations(user_id, db, limit=5)
    if not recommended_product_ids:
        raise HTTPException(status_code=404, detail="User not found or no recommendations available")
    recommended_products = db.query(Product).filter(Product.product_id.in_(recommended_product_ids)).all()
    return recommended_products

@router.get("/{user_id}/explain/{product_id}", response_model=str, summary="Explain Recommendation",
            description="Get an explanation for why a product was recommended.",
            responses={200: {"description": "Successful Response"},
                       404: {"description": "User or Product not found"}
                       }
            )
async def get_recommendation_explanation(user_id: int, product_id: int, db: Session = Depends(database.get_db)):
    """
    Get an explanation for why a product was recommended.
    """
    explanation = await explain_recommendation(user_id, product_id, db)
    if explanation is None:
        user_exists = db.query(models.User).filter_by(user_id=user_id).first() is not None
        product_exists = db.query(models.Product).filter_by(product_id=product_id).first() is not None
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found")
        if not product_exists:
            raise HTTPException(status_code=404, detail="Product not found")
    return explanation
