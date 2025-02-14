from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ProductBase(BaseModel):
    name: str
    category: str
    tags: Optional[List[str]]
    rating: float

class ProductResponse(ProductBase):
    product_id: int

    class Config:
        orm_mode = True
