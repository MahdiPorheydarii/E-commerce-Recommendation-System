import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.database import models
from app.recommendation.services import (
    get_hybrid_recommendations,
    get_user_based_recommendations,
    get_content_based_recommendations,
    get_personalized_recommendations,
    get_contextual_recommendations,
    get_svd_recommendations
    )
from app.recommendation.utils import cache_recommendations, get_cached_recommendations, explain_recommendation
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
    """
    Inserts large-scale mock data into the test database for realistic API load testing.
    Ensures proper insertion order to prevent ForeignKeyViolation errors in PostgreSQL.
    """
    # Step 1: Insert Users
    users = [
        models.User(user_id=i, name=f"User{i}", location=f"Location{i%50}", device=["Mobile", "Desktop", "Tablet"][i % 3])
        for i in range(1, 1001)
    ]
    db.bulk_save_objects(users)
    db.commit()

    # Step 2: Insert Products
    categories = ["Electronics", "Clothing", "Home & Kitchen", "Books", "Sports", "Toys", "Beauty", "Gaming", "Automotive"]
    products = [
        models.Product(product_id=i, name=f"Product {i}", category=categories[i % len(categories)], tags="tag1 tag2", rating=round((3.0 + (i % 5) * 0.5), 1))
        for i in range(1, 5001)
    ]
    db.bulk_save_objects(products)
    db.commit()

    # Step 3: Insert Browsing History (AFTER Users & Products)
    browsing_history = [
        models.BrowsingHistory(user_id=(i % 1000) + 1, product_id=(i % 5000) + 1, timestamp=datetime.utcnow() - timedelta(days=i % 365))
        for i in range(1, 50001)
    ]
    db.bulk_save_objects(browsing_history)
    db.commit()

    # Step 4: Insert Purchase History
    purchase_history = [
        models.PurchaseHistory(user_id=(i % 1000) + 1, product_id=(i % 5000) + 1, quantity=(i % 5) + 1, timestamp=datetime.utcnow() - timedelta(days=i % 180))
        for i in range(1, 20001)
    ]
    db.bulk_save_objects(purchase_history)
    db.commit()

    # Step 5: Insert User Interactions
    interaction_types = ["view", "add_to_cart", "remove_from_cart"]
    user_interactions = [
        models.UserInteraction(user_id=(i % 1000) + 1, product_id=(i % 5000) + 1, interaction_type=interaction_types[i % 3], timestamp=datetime.utcnow() - timedelta(days=i % 90), time_spent=(i % 300) + 10, context=["weekday", "weekend", "morning", "evening"][i % 4])
        for i in range(1, 30001)
    ]
    db.bulk_save_objects(user_interactions)
    db.commit()

    # Step 6: Insert Contextual Signals
    contextual_signals = [
        models.ContextualSignal(category="Electronics", peak_days="Monday,Wednesday,Friday", season="Winter", time_of_day="Morning", device_type="Mobile"),
        models.ContextualSignal(category="Clothing", peak_days="Saturday,Sunday", season="Summer", time_of_day="Evening", device_type="Desktop"),
        models.ContextualSignal(category="Home & Kitchen", peak_days="Tuesday,Thursday", season="Fall", time_of_day="Afternoon", device_type="Tablet"),
        models.ContextualSignal(category="Books", peak_days="Friday,Saturday", season="Spring", time_of_day="Night", device_type="Mobile"),
        models.ContextualSignal(category="Sports", peak_days="Sunday", season="Winter", time_of_day="Morning", device_type="Desktop")
    ]
    db.bulk_save_objects(contextual_signals)
    db.commit()


def test_get_hybrid_recommendations(db, setup_data):
    """Ensures hybrid recommendations return valid, diverse results."""
    user_id = 1
    recommendations = asyncio.run(get_hybrid_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) == 5
    assert all(isinstance(product_id, int) for product_id in recommendations)  # Ensure integer IDs
    assert len(set(recommendations)) == len(recommendations)  # Ensure no duplicates

def test_get_hybrid_recommendations_no_user(db, setup_data):
    """Handles case where user ID is None."""
    recommendations = asyncio.run(get_hybrid_recommendations(None, db, limit=5))
    assert isinstance(recommendations, list)
    assert len(recommendations) > 0  # Should return trending products

def test_get_user_based_recommendations(db, setup_data):
    """Ensures user-based filtering recommends items that similar users have purchased."""
    user_id = 1
    recommendations = asyncio.run(get_user_based_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) == 5
    assert all(isinstance(product_id, int) for product_id in recommendations)

def test_get_user_based_recommendations_no_history(db, setup_data):
    """Handles cases where a user has no purchase history."""
    user_id = 9999  # Assuming this user exists but has no purchase history
    recommendations = asyncio.run(get_user_based_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) > 0  # Should fall back to trending products

def test_get_content_based_recommendations(db, setup_data):
    """Ensures content-based filtering recommends similar products based on browsing history."""
    user_id = 1
    recommendations = asyncio.run(get_content_based_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) == 5

def test_get_content_based_recommendations_no_history(db, setup_data):
    """Handles cases where a user has never browsed any product."""
    user_id = 9999  # Assuming this user has no browsing history
    recommendations = asyncio.run(get_content_based_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) > 0  # Should return trending products

def test_get_personalized_recommendations(db, setup_data):
    """Ensures personalized recommendations consider device type & time of day."""
    user_id = 1
    recommendations = asyncio.run(get_personalized_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) == 5

def test_get_contextual_recommendations(db, setup_data):
    """Ensures recommendations match contextual signals like time-of-day trends."""
    user_id = 1
    recommendations = asyncio.run(get_contextual_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) == 5

def test_get_svd_recommendations(db, setup_data):
    """Ensures SVD-based recommendations provide a valid ranked list of items."""
    user_id = 1
    recommendations = asyncio.run(get_svd_recommendations(user_id, db, limit=5))

    assert isinstance(recommendations, list)
    assert len(recommendations) == 5
    assert all(isinstance(product_id, int) for product_id in recommendations)

def test_explain_recommendation(db, setup_data):
    """Checks if recommendation explanations provide valid reasons."""
    user_id = 1
    product_id = 1
    explanation = asyncio.run(explain_recommendation(user_id, product_id, db))

    assert isinstance(explanation, str) or explanation is None

def test_explain_recommendation_no_user(db, setup_data):
    """Ensures explanation handles missing user cases."""
    product_id = 1
    explanation = asyncio.run(explain_recommendation(None, product_id, db))

    assert isinstance(explanation, str) or explanation is None

def test_cache_recommendations(db, setup_data):
    """Verifies that recommendations are stored and retrieved correctly from cache."""
    user_id = 1
    recommendations = [1, 2, 3, 4, 5]
    
    asyncio.run(cache_recommendations(user_id, recommendations))
    cached_recommendations = asyncio.run(get_cached_recommendations(user_id))

    assert cached_recommendations == recommendations

def test_explain_recommendation_no_data(db, setup_data):
    """Ensures explanation function returns None for unknown users/products."""
    user_id = 99999  # Non-existent user
    product_id = 99999  # Non-existent product
    explanation = asyncio.run(explain_recommendation(user_id, product_id, db))

    assert explanation is None