from locust import HttpUser, between, task
import logging

logger = logging.getLogger(__name__)


class PrincipalUser(HttpUser):
    """User with calco2.user.principal role - unit-level manager with unit-scope access."""

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Authenticate as principal user."""
        login_url = f"{self.host}/api/v1/auth/login-test?role=co2.user.principal"
        resp = self.client.get(login_url, allow_redirects=True, name="login-test")
        if resp.status_code not in (200, 302):
            logger.warning(f"Login failed with status {resp.status_code}")

    @task
    def login_test(self):
        self.client.get(
            "/api/v1/auth/login-test?role=co2.user.principal", name="login-test"
        )

    @task
    def get_me(self):
        self.client.get("/api/v1/auth/me", name="GET /auth/me")

    @task(3)
    def get_user_units(self):
        self.client.get("/api/v1/users/units?skip=0&limit=100", name="GET /users/units")

    @task(3)
    def get_unit_results(self):
        self.client.get("/api/v1/unit/1/results", name="GET /unit/{id}/results")

    @task(2)
    def get_unit_totals(self):
        self.client.get(
            "/api/v1/unit/1/2024/totals", name="GET /unit/{id}/{year}/totals"
        )

    @task(1)
    def get_validated_emissions(self):
        self.client.get(
            "/api/v1/unit/1/yearly-validated-emissions",
            name="GET /unit/{id}/yearly-validated-emissions",
        )

    @task(3)
    def get_module(self):
        self.client.get(
            "/api/v1/modules/1/2024/headcount",
            name="GET /modules/{unit}/{year}/{module}",
        )

    @task(2)
    def get_module_stats_by_class(self):
        self.client.get(
            "/api/v1/modules/1/2024/headcount/stats-by-class",
            name="GET /modules/{unit}/{year}/{module}/stats-by-class",
        )

    @task(2)
    def get_evolution_over_time(self):
        self.client.get(
            "/api/v1/modules/1/evolution-over-time",
            name="GET /modules/{unit}/evolution-over-time",
        )

    @task(1)
    def get_building_rooms(self):
        self.client.get(
            "/api/v1/modules/building-rooms", name="GET /modules/building-rooms"
        )

    @task(3)
    def get_units(self):
        self.client.get("/api/v1/units", name="GET /units")


class BackofficeUser(HttpUser):
    """User with calco2.backoffice.metier role - backoffice admin with reporting/data access."""

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Authenticate as backoffice user."""
        login_url = f"{self.host}/api/v1/auth/login-test?role=co2.backoffice.metier"
        resp = self.client.get(login_url, allow_redirects=True, name="login-test")
        if resp.status_code not in (200, 302):
            logger.warning(f"Login failed with status {resp.status_code}")

    @task
    def login_test(self):
        self.client.get(
            "/api/v1/auth/login-test?role=co2.backoffice.metier", name="login-test"
        )

    @task
    def get_me(self):
        self.client.get("/api/v1/auth/me", name="GET /auth/me")

    @task(3)
    def get_backoffice_units(self):
        self.client.get("/api/v1/backoffice/units", name="GET /backoffice/units")

    @task(2)
    def get_backoffice_unit(self):
        self.client.get("/api/v1/backoffice/unit/1", name="GET /backoffice/unit/{id}")

    @task(2)
    def get_backoffice_years(self):
        self.client.get("/api/v1/backoffice/years", name="GET /backoffice/years")

    @task(1)
    def export_detailed(self):
        self.client.get(
            "/api/v1/backoffice/export-detailed", name="GET /backoffice/export-detailed"
        )

    @task(1)
    def export_reporting(self):
        self.client.get("/api/v1/backoffice/export", name="GET /backoffice/export")

    @task(2)
    def get_reporting_units(self):
        self.client.get(
            "/api/v1/backoffice-reporting/units", name="GET /backoffice-reporting/units"
        )

    @task(2)
    def get_jobs_by_status(self):
        self.client.get("/api/v1/sync/jobs/by-status", name="GET /sync/jobs/by-status")

    @task(1)
    def get_job_stream(self):
        self.client.get("/api/v1/sync/jobs/stream", name="GET /sync/jobs/stream")

    @task(2)
    def list_files(self):
        self.client.get("/api/v1/files/", name="GET /files/")


class SuperAdminUser(HttpUser):
    """User with calco2.superadmin role - full system access."""

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Authenticate as super admin."""
        login_url = f"{self.host}/api/v1/auth/login-test?role=co2.superadmin"
        resp = self.client.get(login_url, allow_redirects=True, name="login-test")
        if resp.status_code not in (200, 302):
            logger.warning(f"Login failed with status {resp.status_code}")

    @task
    def login_test(self):
        self.client.get(
            "/api/v1/auth/login-test?role=co2.superadmin", name="login-test"
        )

    @task
    def get_me(self):
        self.client.get("/api/v1/auth/me", name="GET /auth/me")

    @task(3)
    def get_audit_logs(self):
        self.client.get("/api/v1/audit/activity", name="GET /audit/activity")

    @task(2)
    def get_audit_stats(self):
        self.client.get("/api/v1/audit/stats", name="GET /audit/stats")

    @task(1)
    def get_audit_log_detail(self):
        self.client.get("/api/v1/audit/activity/1", name="GET /audit/activity/{id}")

    @task(1)
    def export_audit_logs(self):
        self.client.get("/api/v1/audit/export", name="GET /audit/export")

    @task(2)
    def sync_data_entries(self):
        self.client.post(
            "/api/v1/sync/data-entries/1",
            json={"config": "test"},
            name="POST /sync/data-entries/{id}",
        )

    @task(1)
    def sync_factors(self):
        self.client.post(
            "/api/v1/sync/factors/1/1",
            json={"config": "test"},
            name="POST /sync/factors/{module}/{factor}",
        )

    @task(3)
    def get_module_stats(self):
        self.client.get(
            "/api/v1/modules-stats/1/2024/headcount/stats",
            name="GET /modules-stats/{unit}/{year}/{module}/stats",
        )

    @task(1)
    def create_carbon_report(self):
        payload = {"unit_id": 1, "year": 2024}
        self.client.post(
            "/api/v1/carbon-reports/", json=payload, name="POST /carbon-reports/"
        )


class StandardUser(HttpUser):
    """User with calco2.user.std role - basic user with own-scope access."""

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Authenticate as standard user."""
        login_url = f"{self.host}/api/v1/auth/login-test?role=co2.user.std"
        resp = self.client.get(login_url, allow_redirects=True, name="login-test")
        if resp.status_code not in (200, 302):
            logger.warning(f"Login failed with status {resp.status_code}")

    @task
    def login_test(self):
        self.client.get("/api/v1/auth/login-test?role=co2.user.std", name="login-test")

    @task
    def get_me(self):
        self.client.get("/api/v1/auth/me", name="GET /auth/me")

    @task(3)
    def get_user_units(self):
        self.client.get("/api/v1/users/units?skip=0&limit=100", name="GET /users/units")

    @task(3)
    def get_units(self):
        self.client.get("/api/v1/units", name="GET /units")
