"""Test resource service."""

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.resource import Resource
from app.models.user import User
from app.schemas.resource import ResourceCreate
from app.services import resource_service

standar_user_role = {
    "role": "co2.user.std",
    "on": {"unit": "12345"},
}

other_user_role = {
    "role": "co2.user.std",
    "on": {"unit": "67890"},
}


admin_user_role = {
    "role": "co2.backoffice.admin",
    "on": "global",
}


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user for testing."""
    user = User(
        id="test@example.com",
        email="test@example.com",
        roles=[standar_user_role],
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_resource(db_session, test_user):
    """Create a test resource for testing."""
    resource = Resource(
        name="Test Resource",
        description="Test Description",
        unit_id=test_user.roles[0]["on"]["unit"],
        owner_id=test_user.id,
        visibility="private",
        data={"key": "value"},
    )
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)
    return resource


@pytest.mark.asyncio
async def test_list_resources_with_opa_allow(
    db_session, test_user, test_resource, mock_policy_allow
):
    """Test listing resources when OPA allows."""
    resources = await resource_service.list_resources(db=db_session, user=test_user)
    assert len(resources) > 0
    assert resources[0].id == test_resource.id


@pytest.mark.asyncio
async def test_list_resources_with_opa_deny(
    db_session, test_user, test_resource, mock_policy_deny
):
    """Test listing resources when OPA denies."""
    with pytest.raises(HTTPException) as exc_info:
        await resource_service.list_resources(db=db_session, user=test_user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_resource_success(
    db_session, test_user, test_resource, mock_policy_allow
):
    """Test getting a resource successfully."""
    resource = await resource_service.get_resource(
        db=db_session, resource_id=test_resource.id, user=test_user
    )
    assert resource is not None
    assert resource.id == test_resource.id


@pytest.mark.asyncio
async def test_get_resource_not_found(db_session, test_user, mock_policy_allow):
    """Test getting a non-existent resource."""
    with pytest.raises(HTTPException) as exc_info:
        await resource_service.get_resource(
            db=db_session, resource_id=99999, user=test_user
        )
    assert exc_info.value.status_code == 404


@pytest.fixture
def sample_resource_data(test_user):
    """Sample resource data for testing."""
    return {
        "name": "Test Resource",
        "description": "Test Description",
        "unit_id": test_user.roles[0]["on"]["unit"],
        "visibility": "private",
        "data": {"key": "value"},
        "metadata": {"test": True},
    }


@pytest.mark.asyncio
async def test_create_resource(
    db_session, test_user, mock_policy_allow, sample_resource_data
):
    """Test creating a resource."""
    resource_data = ResourceCreate(**sample_resource_data)

    resource = await resource_service.create_resource(
        db=db_session, resource_in=resource_data, user=test_user
    )

    assert resource is not None
    assert resource.name == sample_resource_data["name"]
    assert resource.owner_id == test_user.id


@pytest.fixture
def sample_resource_denied_data():
    """Sample resource data for testing."""
    return {
        "name": "Test Resource",
        "description": "Test Description",
        "unit_id": other_user_role["on"]["unit"],
        "visibility": "private",
        "data": {"key": "value"},
        "metadata": {"test": True},
    }


@pytest.mark.asyncio
async def test_create_resource_denied(
    db_session, test_user, mock_policy_deny, sample_resource_denied_data
):
    """Test creating a resource when denied."""
    resource_data = ResourceCreate(**sample_resource_denied_data)

    with pytest.raises(HTTPException) as exc_info:
        await resource_service.create_resource(
            db=db_session, resource_in=resource_data, user=test_user
        )
    assert exc_info.value.status_code == 403
