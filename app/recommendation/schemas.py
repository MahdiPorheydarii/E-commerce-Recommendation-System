from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class UserBase(BaseModel):
    name: str
    location: str
    device: str

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    user_id: int

    class Config:
        orm_mode = True

class ProductBase(BaseModel):
    name: str
    category: str
    tags: Optional[List[str]]
    rating: float

class ProductResponse(ProductBase):
    product_id: int

    class Config:
        orm_mode = True

class BrowsingHistoryBase(BaseModel):
    user_id: int
    product_id: int
    timestamp: datetime

class PurchaseHistoryBase(BaseModel):
    user_id: int
    product_id: int
    quantity: int
    timestamp: datetime
