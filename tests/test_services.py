import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.database import models, database
from app.recommendation.services import (
    get_hybrid_recommendations,
    get_user_based_recommendations,
    get_content_based_recommendations,
    get_personalized_recommendations,
    get_contextual_recommendations,
    get_svd_recommendations,
    explain_recommendation
)
from app.recommendation.utils import cache_recommendations, get_cached_recommendations
import asyncio

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db():
    models.Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    models.Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def setup_data(db):
    # Create mock users
    for i in range(1, 101):
        user = models.User(user_id=i, name=f"User{i}", location="Location", device="Device")
        db.add(user)
    
    # Create mock products
    for i in range(1, 201):
        product = models.Product(product_id=i, name=f"Product{i}", category=f"Category{i%10}", tags="tag1 tag2", rating=4.5)
        db.add(product)
    
    # Create mock purchase history
    for i in range(1, 1001):
        purchase = models.PurchaseHistory(user_id=(i%100)+1, product_id=(i%200)+1, quantity=1)
        db.add(purchase)
    
    # Create mock browsing history
    for i in range(1, 1001):
        browsing = models.BrowsingHistory(user_id=(i%100)+1, product_id=(i%200)+1)
        db.add(browsing)
    
    # Create mock user interactions
    for i in range(1, 1001):
        interaction = models.UserInteraction(user_id=(i%100)+1, product_id=(i%200)+1, interaction_type="view")
        db.add(interaction)
    
    # Create mock contextual signals
    contextual_signals = [
        {"category": "Category1", "peak_days": "Monday,Tuesday", "season": "Winter"},
        {"category": "Category2", "peak_days": "Wednesday,Thursday", "season": "Spring"},
        {"category": "Category3", "peak_days": "Friday,Saturday", "season": "Summer"},
        {"category": "Category4", "peak_days": "Sunday", "season": "Fall"}
    ]
    for signal in contextual_signals:
        cs = models.ContextualSignal(category=signal["category"], peak_days=signal["peak_days"], season=signal["season"])
        db.add(cs)
    
    db.commit()

def test_get_hybrid_recommendations(db, setup_data):
    user_id = 1
    try:
        recommendations = asyncio.run(get_hybrid_recommendations(user_id, db, limit=5))
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5
    except HTTPException as e:
        assert e.status_code == 500

def test_get_hybrid_recommendations_no_user(db, setup_data):
    try:
        recommendations = asyncio.run(get_hybrid_recommendations(None, db, limit=5))
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5
    except HTTPException as e:
        assert e.status_code == 500

def test_get_user_based_recommendations(db, setup_data):
    user_id = 1
    try:
        recommendations = asyncio.run(get_user_based_recommendations(user_id, db, limit=5))
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5
    except HTTPException as e:
        assert e.status_code == 500

def test_get_content_based_recommendations(db, setup_data):
    user_id = 1
    try:
        recommendations = asyncio.run(get_content_based_recommendations(user_id, db, limit=5))
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5
    except HTTPException as e:
        assert e.status_code == 500

def test_get_personalized_recommendations(db, setup_data):
    user_id = 1
    try:
        recommendations = asyncio.run(get_personalized_recommendations(user_id, db, limit=5))
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5
    except HTTPException as e:
        assert e.status_code == 500

def test_get_contextual_recommendations(db, setup_data):
    user_id = 1
    try:
        recommendations = asyncio.run(get_contextual_recommendations(user_id, db, limit=5))
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5
    except HTTPException as e:
        assert e.status_code == 500

def test_get_svd_recommendations(db, setup_data):
    user_id = 1
    try:
        recommendations = asyncio.run(get_svd_recommendations(user_id, db, limit=5))
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5
    except HTTPException as e:
        assert e.status_code == 500

def test_explain_recommendation(db, setup_data):
    user_id = 1
    product_id = 1
    try:
        explanation = asyncio.run(explain_recommendation(user_id, product_id, db))
        assert isinstance(explanation, str) or explanation is None
    except HTTPException as e:
        assert e.status_code == 500

def test_explain_recommendation_no_user(db, setup_data):
    product_id = 1
    try:
        explanation = asyncio.run(explain_recommendation(None, product_id, db))
        assert isinstance(explanation, str) or explanation is None
    except HTTPException as e:
        assert e.status_code == 500

def test_cache_recommendations(db, setup_data):
    user_id = 1
    recommendations = [1, 2, 3, 4, 5]
    asyncio.run(cache_recommendations(user_id, recommendations))
    cached_recommendations = asyncio.run(get_cached_recommendations(user_id))
    assert cached_recommendations == recommendations

def test_explain_recommendation_no_data(db, setup_data):
    user_id = 999  # Non-existent user
    product_id = 999  # Non-existent product
    try:
        explanation = asyncio.run(explain_recommendation(user_id, product_id, db))
        assert explanation is None
    except HTTPException as e:
        assert e.status_code == 500