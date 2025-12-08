"""Test resource service."""

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.user import GlobalScope, Role, RoleName, RoleScope
from app.providers.role_provider import get_role_provider
from app.repositories.resource_repo import create_resource
from app.repositories.user_repo import upsert_user
from app.schemas.resource import ResourceCreate
from app.services import resource_service

TEST_UNIT_ID = "12345"
OTHER_UNIT_ID = "67890"

standar_user_role = Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit=TEST_UNIT_ID))
other_user_role = Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit=OTHER_UNIT_ID))
admin_user_role = Role(role=RoleName.CO2_BACKOFFICE_ADMIN, on=GlobalScope())


@pytest_asyncio.fixture
async def test_unit():
    return TEST_UNIT_ID


@pytest_asyncio.fixture
async def other_unit():
    return OTHER_UNIT_ID


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user for testing."""
    role_provider = get_role_provider("test")
    testuser_info = {
        "requested_role": "co2.user.std",
        "email": "testuser_co2.user.std@example.org",
    }
    sciper = role_provider.get_sciper(testuser_info)
    roles = await role_provider.get_roles(testuser_info)
    user = await upsert_user(
        db=db_session,
        email=testuser_info.get("email"),
        sciper=sciper,
        roles=roles,
    )
    return user


@pytest_asyncio.fixture
async def test_resource(db_session, test_user, test_unit):
    """Create a test resource for testing."""

    resource = await create_resource(
        db=db_session,
        resource=ResourceCreate(
            name="Initial Resource",
            description="Initial Description",
            unit_id=test_unit,
            visibility="private",
            data={"initial": "data"},
            resource_metadata={"foo": "bar"},
        ),
        user_id=test_user.id,
    )
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
def sample_resource_data():
    """Sample resource data for testing."""
    return ResourceCreate(
        name="Test Resource",
        description="Test Description",
        unit_id=TEST_UNIT_ID,
        visibility="private",
        data={"key": "value"},
        resource_metadata={"test": True},
    )


@pytest.mark.asyncio
async def test_create_resource(
    db_session, test_user, mock_policy_allow, sample_resource_data
):
    """Test creating a resource."""

    resource = await resource_service.create_resource(
        db=db_session, resource_in=sample_resource_data, user=test_user
    )

    assert resource is not None
    assert resource.name == sample_resource_data.name
    assert resource.created_by == test_user.id


@pytest.fixture
def sample_resource_denied_data(other_unit):
    """Sample resource data for testing."""
    return {
        "name": "Test Resource",
        "description": "Test Description",
        "unit_id": other_unit,
        "visibility": "private",
        "data": {"key": "value"},
        "resource_metadata": {"test": True},
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
