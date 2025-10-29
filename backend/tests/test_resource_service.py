"""Test resource service."""

import pytest
from fastapi import HTTPException

from app.models.resource import Resource
from app.models.user import User
from app.schemas.resource import ResourceCreate
from app.services import resource_service


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        id="test@example.com",
        email="test@example.com",
        hashed_password="hashed",
        unit_id="ENAC",
        roles=["user"],
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_resource(db_session, sample_user):
    """Create a sample resource for testing."""
    resource = Resource(
        name="Test Resource",
        description="Test Description",
        unit_id="ENAC",
        owner_id=sample_user.id,
        visibility="private",
        data={"key": "value"},
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


def test_list_resources_with_opa_allow(
    db_session, sample_user, sample_resource, mock_opa_allow
):
    """Test listing resources when OPA allows."""
    resources = resource_service.list_resources(db_session, sample_user)
    assert len(resources) > 0


def test_list_resources_with_opa_deny(
    db_session, sample_user, sample_resource, mock_opa_deny
):
    """Test listing resources when OPA denies."""
    resources = resource_service.list_resources(db_session, sample_user)
    assert len(resources) == 0


def test_get_resource_success(db_session, sample_user, sample_resource, mock_opa_allow):
    """Test getting a specific resource."""
    resource = resource_service.get_resource(
        db_session, sample_resource.id, sample_user
    )
    assert resource.id == sample_resource.id


def test_get_resource_not_found(db_session, sample_user, mock_opa_allow):
    """Test getting a non-existent resource."""
    with pytest.raises(HTTPException) as exc:
        resource_service.get_resource(db_session, 99999, sample_user)
    assert exc.value.status_code == 404


def test_create_resource(db_session, sample_user, mock_opa_allow):
    """Test creating a new resource."""
    resource_data = ResourceCreate(
        name="New Resource",
        description="New Description",
        unit_id="ENAC",
        visibility="private",
        data={"key": "value"},
    )

    resource = resource_service.create_resource(db_session, resource_data, sample_user)
    assert resource.name == "New Resource"
    assert resource.owner_id == sample_user.id


def test_create_resource_denied(db_session, sample_user, mock_opa_deny):
    """Test creating a resource when OPA denies."""
    resource_data = ResourceCreate(
        name="New Resource",
        unit_id="ENAC",
        visibility="private",
    )

    with pytest.raises(HTTPException) as exc:
        resource_service.create_resource(db_session, resource_data, sample_user)
    assert exc.value.status_code == 403
