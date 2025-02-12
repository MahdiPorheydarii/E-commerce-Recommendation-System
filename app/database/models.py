from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    device = Column(String, nullable=False)
    browsing_history = relationship("BrowsingHistory", back_populates="user")
    purchase_history = relationship("PurchaseHistory", back_populates="user")
    interactions = relationship("UserInteraction", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    tags = Column(String, nullable=True)
    rating = Column(Float, nullable=False)
    metadata = Column(Text, nullable=True)

class BrowsingHistory(Base):
    __tablename__ = "browsing_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="browsing_history")
    product = relationship("Product")

class PurchaseHistory(Base):
    __tablename__ = "purchase_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="purchase_history")
    product = relationship("Product")

class UserInteraction(Base):
    __tablename__ = "user_interactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    interaction_type = Column(String, nullable=False)  # e.g., click, view, time_spent
    timestamp = Column(DateTime, default=datetime.utcnow)
    time_spent = Column(Integer, nullable=True)  # Time spent in seconds
    context = Column(String, nullable=True)  # e.g., time_of_day, day_of_week, device_type
    user = relationship("User", back_populates="interactions")
    product = relationship("Product")
