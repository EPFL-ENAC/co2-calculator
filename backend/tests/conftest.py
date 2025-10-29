"""Test configuration for pytest."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app

# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a new database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with database override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_opa_allow(monkeypatch):
    """Mock OPA to always allow with no filters."""
    from app.core import opa_client

    def mock_query(*args, **kwargs):
        return {"allow": True, "filters": {}}

    monkeypatch.setattr(opa_client, "query_opa", mock_query)


@pytest.fixture
def mock_opa_deny(monkeypatch):
    """Mock OPA to always deny."""
    from app.core import opa_client

    def mock_query(*args, **kwargs):
        return {"allow": False, "reason": "Access denied"}

    monkeypatch.setattr(opa_client, "query_opa", mock_query)
