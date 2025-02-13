from locust import HttpUser, task, between

class RecommendationUser(HttpUser):
    wait_time = between(1, 3)  # Simulates real-world user behavior

    @task
    def get_recommendations(self):
        self.client.get("/recommendations/1")  # Replace 1 with a test user ID
