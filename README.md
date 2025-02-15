# E-commerce-Recommendation-System
## Overview
This project implements a hybrid recommendation system for an e-commerce platform, combining collaborative filtering, content-based filtering, contextual recommendations, and matrix factorization (SVD). The system is designed to provide personalized, diverse, and scalable product recommendations while addressing challenges like cold starts and large-scale data processing.

## **Explanation of Each Component**
- **`app/`** - Contains the core application logic.
  - **`database/`** - Handles database connection, models, and initialization.
  - **`recommendation/`** - Implements recommendation logic, utilities, and scheduling.
  - **`config.py`** - Stores configuration settings.
  - **`main.py`** - The entry point for the FastAPI server.
- **`tests/`** - Contains unit and integration tests.
- **`env/`** - Used for environment-specific configurations.
- **`.env`** - Stores sensitive environment variables (e.g., database credentials).
- **`.gitignore`** - Specifies files and directories to ignore in Git.
- **`compose.yaml`** - Defines multi-container application services for Docker Compose.
- **`Dockerfile`** - Instructions to build a Docker image.
- **`requirements.txt`** - Lists dependencies needed for the project.


## **Setup Instructions**

### **1 Clone the Repository**
```sh
git clone https://github.com/MahdiPorheydarii/E-commerce-Recommendation-System
cd E-commerce-Recommendation-System
```

### **2 Environment Variables**
Create a `.env` file in the root directory with the following:
```
POSTGRES_USER=user
POSTGRES_PASSWORD=pw
POSTGRES_DB=db

REDIS_PASSWORD=pass
```

### **3 Running with Docker Compose**
Build and start the containers:
```sh
docker-compose up --build
```
This will:
- Start the FastAPI app
- Set up a PostgreSQL database
- Launch a Redis cache for faster recommendations

### **4 Running Locally (Without Docker)**
#### **Install Dependencies**
```sh
python -m venv venv
source venv/bin/activate
# On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

#### **Start PostgreSQL and Redis**
Ensure PostgreSQL and Redis are running locally.

#### **Start FastAPI Server**
```sh
uvicorn app.main:app --reload
```

---

## **Overview of the Recommendation Algorithm**

The recommendation system uses a **hybrid approach**, combining multiple techniques:

### **1 User-Based Collaborative Filtering**
- Identifies similar users based on purchase history.
- Recommends products that similar users have purchased.

### **2 Content-Based Filtering**
- Uses product metadata (category, tags, and rating) to find similar products.
- Applies cosine similarity for recommendations.

### **3 Matrix Factorization (SVD)**
- Uses **Singular Value Decomposition (SVD)** to predict user-product affinity.
- Handles missing values and ensures valid recommendations.

### **4 Context-Based Recommendations**
- Uses **time of day, device type, and seasonal trends** to personalize results.

### **5 Hybrid Model and Caching**
- **Combines all the above techniques** for more accurate recommendations.
- **Caches results in Redis** to improve response time and reduce database queries.

---

## **API Endpoints**

### **1. Get Recommendations for a User**
**Request:**
```sh
GET /recommendations/{user_id}?limit={limit}
```
**Parameters:**

- `user_id` (int, required): The ID of the user to get recommendations for.

- `limit` (int, optional, default=10): The number of recommendations to return.
**Response:**
```json
{
  "recommendations": [101, 205, 309, 410, 512]
}
```

### **2. Explain a Recommendation**
**Request:**
```sh
GET /recommendations/{user_id}/explain/{product_id}
```
**Parameters:**

- `user_id` (int, required): The ID of the user.

- `product_id` (int, required): The product for which the recommendation explanation is requested.

**Response:**
```json
"Recommended because users similar to you purchased this."
```

---

## **Testing**
### **Running Tests**
```sh
pytest tests/
```