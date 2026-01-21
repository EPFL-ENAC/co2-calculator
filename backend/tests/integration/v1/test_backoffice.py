"""Integration tests for backoffice API endpoints."""

from unittest.mock import Mock

import pytest
from httpx import AsyncClient

from app.api.deps import get_current_active_user
from app.main import app


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock()
    user.id = 1
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_current_user(mock_user, monkeypatch):
    """Mock the get_current_active_user dependency."""

    async def override_get_current_active_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    yield mock_user
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_backoffice_units(client: AsyncClient, mock_current_user):
    """Test listing backoffice units without filters."""
    response = await client.get("/api/v1/backoffice/units")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Check structure of first unit
    if data:
        unit = data[0]
        assert "id" in unit
        assert "unit" in unit
        assert "affiliation" in unit
        assert "completion" in unit
        assert "completion_counts" in unit
        assert "outlier_values" in unit


@pytest.mark.asyncio
async def test_list_backoffice_units_with_affiliation_filter(
    client: AsyncClient, mock_current_user
):
    """Test listing backoffice units with affiliation filter."""
    response = await client.get(
        "/api/v1/backoffice/units", params={"affiliation": ["ENAC"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # All units should have ENAC affiliation
    for unit in data:
        assert unit["affiliation"] == "ENAC"


@pytest.mark.asyncio
async def test_list_backoffice_units_with_units_filter(
    client: AsyncClient, mock_current_user
):
    """Test listing backoffice units with units filter."""
    response = await client.get("/api/v1/backoffice/units", params={"units": ["ALICE"]})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # All units should be ALICE
    for unit in data:
        assert unit["unit"] == "ALICE"


@pytest.mark.asyncio
async def test_list_backoffice_units_with_completion_filter(
    client: AsyncClient, mock_current_user
):
    """Test listing backoffice units with completion filter."""
    response = await client.get(
        "/api/v1/backoffice/units", params={"completion": "complete"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_backoffice_units_with_years_filter(
    client: AsyncClient, mock_current_user
):
    """Test listing backoffice units with years filter."""
    response = await client.get(
        "/api/v1/backoffice/units", params={"years": ["2024", "2025"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Check that expected_total is calculated correctly (7 modules * 2 years = 14)
    for unit in data:
        if unit.get("expected_total") is not None:
            assert unit["expected_total"] == 14


@pytest.mark.asyncio
async def test_list_backoffice_units_with_search(
    client: AsyncClient, mock_current_user
):
    """Test listing backoffice units with search filter."""
    response = await client.get("/api/v1/backoffice/units", params={"search": "ALICE"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # At least one unit should match
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_backoffice_unit(client: AsyncClient, mock_current_user):
    """Test getting a single backoffice unit."""
    response = await client.get("/api/v1/backoffice/unit/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "unit" in data
    assert "completion" in data
    assert "completion_counts" in data
    assert "outlier_values" in data


@pytest.mark.asyncio
async def test_get_backoffice_unit_with_years(client: AsyncClient, mock_current_user):
    """Test getting a backoffice unit with years filter."""
    response = await client.get("/api/v1/backoffice/unit/1", params={"years": ["2024"]})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "completion" in data
    # With one year, expected_total should be 7
    if data.get("expected_total") is not None:
        assert data["expected_total"] == 7


@pytest.mark.asyncio
async def test_get_backoffice_unit_not_found(client: AsyncClient, mock_current_user):
    """Test getting a non-existent backoffice unit."""
    response = await client.get("/api/v1/backoffice/unit/999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()
