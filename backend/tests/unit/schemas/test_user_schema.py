"""Tests for user schemas."""

from app.models.user import User, UserProvider
from app.schemas.user import UserRead


def test_user_read_is_user_test_with_test_provider():
    """Test that is_user_test returns True for TEST provider."""
    user = User(
        id=1,
        email="testuser@example.org",
        provider_code="test123",
        provider=UserProvider.TEST,
        display_name="Test User",
    )
    user_read = UserRead.model_validate(user)

    assert user_read.is_user_test is True
    assert user_read.email == "testuser@example.org"
    assert user_read.id == 1


def test_user_read_is_user_test_with_default_provider():
    """Test that is_user_test returns None for DEFAULT provider."""
    user = User(
        id=2,
        email="realuser@example.org",
        provider_code="real123",
        provider=UserProvider.DEFAULT,
        display_name="Real User",
    )
    user_read = UserRead.model_validate(user)

    assert user_read.is_user_test is None
    assert user_read.email == "realuser@example.org"
    assert user_read.id == 2

    # Verify it's omitted from serialized output
    user_dict = user_read.model_dump(exclude_none=True)
    assert "is_user_test" not in user_dict


def test_user_read_is_user_test_with_accred_provider():
    """Test that is_user_test returns None for ACCRED provider."""
    user = User(
        id=3,
        email="accreduser@example.org",
        provider_code="123456",
        provider=UserProvider.ACCRED,
        display_name="Accred User",
    )
    user_read = UserRead.model_validate(user)

    assert user_read.is_user_test is None
    assert user_read.email == "accreduser@example.org"
    assert user_read.id == 3

    # Verify it's omitted from serialized output
    user_dict = user_read.model_dump(exclude_none=True)
    assert "is_user_test" not in user_dict


def test_user_read_computed_fields_present():
    """Test that all computed fields are present in serialized output."""
    user = User(
        id=4,
        email="user@example.org",
        provider_code="test456",
        provider=UserProvider.TEST,
        display_name="User with Fields",
        roles_raw=[],
    )
    user_read = UserRead.model_validate(user)

    # Serialize to dict to check that computed fields are included
    user_dict = user_read.model_dump()

    assert "is_user_test" in user_dict
    assert "permissions" in user_dict
    assert user_dict["is_user_test"] is True
    assert isinstance(user_dict["permissions"], dict)
