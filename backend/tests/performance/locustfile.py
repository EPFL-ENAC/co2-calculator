from locust import HttpUser, between, task


class APIUser(HttpUser):
    wait_time = between(1, 3)  # seconds between tasks

    @task
    def get_users(self):
        self.client.get("/api/v1/users")

    @task
    def create_user(self):
        payload = {"name": "John", "email": "john@example.com"}
        self.client.post("/api/v1/users", json=payload)
