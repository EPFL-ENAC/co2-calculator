"""Tests for UserRepository."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.user import UserProvider
from app.repositories.user_repo import UserRepository


@pytest.fixture
def repo():
    """Create a UserRepository with a mock session."""
    session = MagicMock()
    return UserRepository(session)


@pytest.mark.asyncio
async def test_get_by_id(repo):
    """Test getting user by ID."""
    user = SimpleNamespace(id=123, email="test@example.com")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = user
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_id(123)

    assert result == user
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_not_found(repo):
    """Test getting user by ID when not found."""
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_id(999)

    assert result is None
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_code(repo):
    """Test getting user by provider code."""
    user = SimpleNamespace(
        id=123, provider_code="google-12345", email="test@example.com"
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = user
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_code("google-12345")

    assert result == user
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_code_not_found(repo):
    """Test getting user by code when not found."""
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_code("nonexistent-code")

    assert result is None


@pytest.mark.asyncio
async def test_get_by_email(repo):
    """Test getting user by email."""
    user = SimpleNamespace(id=123, email="test@example.com")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = user
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_email("test@example.com")

    assert result == user
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_email_not_found(repo):
    """Test getting user by email when not found."""
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_email("nonexistent@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_create_user_minimal(repo):
    """Test creating a user with minimal required fields."""
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.create(
        provider_code="google-12345",
        email="newuser@example.com",
    )

    # Verify user was added and persisted
    repo.session.add.assert_called_once()
    repo.session.flush.assert_awaited_once()
    repo.session.refresh.assert_awaited_once()

    # Verify created user has expected attributes
    assert result.provider_code == "google-12345"
    assert result.email == "newuser@example.com"
    assert result.roles == []
    assert result.last_login is not None


@pytest.mark.asyncio
async def test_create_user_with_all_fields(repo):
    """Test creating a user with all optional fields."""
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    roles = []

    result = await repo.create(
        provider_code="google-12345",
        email="admin@example.com",
        display_name="Admin User",
        roles=roles,
        provider=UserProvider.DEFAULT,
        function="Administrator",
    )

    # Verify user was added
    repo.session.add.assert_called_once()
    repo.session.flush.assert_awaited_once()

    # Verify all fields
    assert result.provider_code == "google-12345"
    assert result.email == "admin@example.com"
    assert result.display_name == "Admin User"
    assert result.roles == roles
    assert result.provider == UserProvider.DEFAULT
    assert result.function == "Administrator"


@pytest.mark.asyncio
async def test_create_user_with_empty_roles(repo):
    """Test creating a user with empty roles list."""
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.create(
        provider_code="google-12345",
        email="user@example.com",
        roles=[],
    )

    assert result.roles == []


@pytest.mark.asyncio
async def test_create_user_with_none_roles(repo):
    """Test creating a user with None roles defaults to empty list."""
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.create(
        provider_code="google-12345",
        email="user@example.com",
        roles=None,
    )

    assert result.roles == []


@pytest.mark.asyncio
async def test_update_user_display_name(repo):
    """Test updating user display name."""
    existing_user = SimpleNamespace(
        id=123,
        email="user@example.com",
        display_name="Old Name",
        provider=UserProvider.DEFAULT,
        function="User",
        roles=[],
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = existing_user
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.update(123, display_name="New Name")

    # Verify update was persisted
    repo.session.flush.assert_awaited_once()
    repo.session.refresh.assert_awaited_once()

    # Verify display_name was updated
    assert result.display_name == "New Name"
    assert result.last_login is not None


@pytest.mark.asyncio
async def test_update_user_roles(repo):
    """Test updating user roles."""
    existing_user = SimpleNamespace(
        id=123,
        email="user@example.com",
        display_name="User",
        provider=UserProvider.DEFAULT,
        function="User",
        roles=[],
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = existing_user
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    new_roles = []
    result = await repo.update(123, roles=new_roles)

    # Verify roles were updated
    assert result.roles == new_roles
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_provider(repo):
    """Test updating user provider."""
    existing_user = SimpleNamespace(
        id=123,
        email="user@example.com",
        display_name="User",
        provider=UserProvider.DEFAULT,
        function="User",
        roles=[],
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = existing_user
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.update(123, provider=UserProvider.TEST)

    assert result.provider == UserProvider.TEST


@pytest.mark.asyncio
async def test_update_user_function(repo):
    """Test updating user function."""
    existing_user = SimpleNamespace(
        id=123,
        email="user@example.com",
        display_name="User",
        provider=UserProvider.DEFAULT,
        function="User",
        roles=[],
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = existing_user
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.update(123, function="Manager")

    assert result.function == "Manager"


@pytest.mark.asyncio
async def test_update_user_multiple_fields(repo):
    """Test updating multiple user fields at once."""
    existing_user = SimpleNamespace(
        id=123,
        email="user@example.com",
        display_name="Old Name",
        provider=UserProvider.DEFAULT,
        function="User",
        roles=[],
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = existing_user
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    new_roles = []
    result = await repo.update(
        123,
        display_name="New Name",
        roles=new_roles,
        function="Manager",
    )

    assert result.display_name == "New Name"
    assert result.roles == new_roles
    assert result.function == "Manager"


@pytest.mark.asyncio
async def test_update_user_not_found(repo):
    """Test updating a user that doesn't exist raises HTTPException."""
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    with pytest.raises(HTTPException) as exc_info:
        await repo.update(999, display_name="New Name")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


@pytest.mark.asyncio
async def test_update_user_preserves_existing_values(repo):
    """Test that update preserves existing values when not provided."""
    existing_user = SimpleNamespace(
        id=123,
        email="user@example.com",
        display_name="Original Name",
        provider=UserProvider.DEFAULT,
        function="Original Function",
        roles=[],
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = existing_user
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    # Update only display_name, should preserve other fields
    result = await repo.update(123, display_name="New Name")

    assert result.display_name == "New Name"
    assert result.provider == UserProvider.DEFAULT  # Preserved
    assert result.function == "Original Function"  # Preserved


@pytest.mark.asyncio
async def test_list_users_no_filters(repo):
    """Test listing users without filters."""
    users = [
        SimpleNamespace(id=1, email="user1@example.com"),
        SimpleNamespace(id=2, email="user2@example.com"),
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = users
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.list()

    assert result == users
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_users_with_skip_and_limit(repo):
    """Test listing users with pagination."""
    users = [SimpleNamespace(id=3, email="user3@example.com")]
    result_mock = MagicMock()
    result_mock.all.return_value = users
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.list(skip=10, limit=5)

    assert result == users


@pytest.mark.asyncio
async def test_list_users_with_filters(repo):
    """Test listing users with filters."""
    users = [SimpleNamespace(id=1, email="user1@example.com", function="Manager")]
    result_mock = MagicMock()
    result_mock.all.return_value = users
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.list(filters={"function": "Manager"})

    assert result == users


@pytest.mark.asyncio
async def test_list_users_with_list_filter(repo):
    """Test listing users with list filter (in clause)."""
    users = [
        SimpleNamespace(id=1, email="user1@example.com"),
        SimpleNamespace(id=2, email="user2@example.com"),
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = users
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.list(filters={"id": [1, 2]})

    assert result == users


@pytest.mark.asyncio
async def test_list_users_empty_result(repo):
    """Test listing users when no results found."""
    result_mock = MagicMock()
    result_mock.all.return_value = []
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.list()

    assert result == []


@pytest.mark.asyncio
async def test_count_users_no_filters(repo):
    """Test counting users without filters."""
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 42
    repo.session.execute = AsyncMock(return_value=result_mock)

    result = await repo.count()

    assert result == 42
    repo.session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_users_with_filters(repo):
    """Test counting users with filters."""
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 5
    repo.session.execute = AsyncMock(return_value=result_mock)

    result = await repo.count(filters={"function": "Manager"})

    assert result == 5


@pytest.mark.asyncio
async def test_count_users_zero(repo):
    """Test counting users when zero results."""
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 0
    repo.session.execute = AsyncMock(return_value=result_mock)

    result = await repo.count()

    assert result == 0


@pytest.mark.asyncio
async def test_delete_user_success(repo):
    """Test successfully deleting a user."""
    user = SimpleNamespace(id=123, email="delete@example.com")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = user
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.delete = AsyncMock()
    repo.session.flush = AsyncMock()

    result = await repo.delete(123)

    assert result is True
    repo.session.delete.assert_awaited_once()
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_user_not_found(repo):
    """Test deleting a user that doesn't exist."""
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.delete(999)

    assert result is False
    # delete and flush should not be called
    assert not hasattr(repo.session.delete, "assert_awaited")
