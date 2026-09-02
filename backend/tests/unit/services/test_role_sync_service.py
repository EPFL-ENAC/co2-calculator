"""Unit tests for RoleSyncService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.unit import Unit
from app.models.user import (
    GlobalScope,
    OwnScope,
    Role,
    RoleName,
    User,
    UserProvider,
)
from app.providers.role_provider import RoleProviderNetworkError
from app.services.role_sync_service import RoleSyncOutcome, RoleSyncService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_sync_roles_detects_changes(db_session):
    """Test that sync detects role changes and updates user."""
    # Arrange
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=[
            {
                "role": RoleName.CO2_USER_STD.value,
                "on": {"kind": "own", "institutional_id": "unit1"},
            }
        ],
        last_roles_sync_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    provider_user = {
        "email": "test@example.com",
        "code": "12345",
        "display_name": "Test User",
        "function": "Tester",
        "roles": [
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="unit2"))
        ],
    }
    mock_provider = AsyncMock()
    mock_provider.get_user_by_user_id = AsyncMock(return_value=provider_user)

    service = RoleSyncService(db_session)

    # Act
    result = await service.sync_user_roles(user.id, mock_provider)

    # Assert
    assert result.has_changed is True
    assert result.roles_changed is True
    mock_provider.get_user_by_user_id.assert_awaited_once_with("12345")
    user_updated = await service.user_repo.get_by_id(user.id)
    assert user_updated.last_roles_sync_at is not None


@pytest.mark.asyncio
async def test_sync_roles_no_changes(db_session):
    """Test that sync skips update when roles unchanged."""
    # Arrange
    roles_raw = [
        {
            "role": RoleName.CO2_USER_STD.value,
            "on": {"kind": "own", "institutional_id": "unit1"},
        }
    ]
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=roles_raw,
        last_roles_sync_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    provider_user = {
        "email": "test@example.com",
        "code": "12345",
        "display_name": "Test User",
        "function": "Tester",
        "roles": [
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="unit1"))
        ],
    }
    mock_provider = AsyncMock()
    mock_provider.get_user_by_user_id = AsyncMock(return_value=provider_user)

    service = RoleSyncService(db_session)

    # Act
    result = await service.sync_user_roles(user.id, mock_provider)

    # Assert
    assert result.has_changed is False
    assert result.roles_changed is False


@pytest.mark.asyncio
async def test_sync_roles_ignores_recent_sync(db_session):
    """Test that sync respects TTL and skips recent syncs
    without calling the provider.
    """
    # Arrange
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=[
            {
                "role": RoleName.CO2_USER_STD.value,
                "on": {"kind": "own", "institutional_id": "unit1"},
            }
        ],
        last_roles_sync_at=datetime.now(UTC),  # Just synced
    )
    db_session.add(user)
    await db_session.commit()

    mock_provider = AsyncMock()
    mock_provider.get_user_by_user_id = AsyncMock()

    service = RoleSyncService(db_session, sync_ttl_minutes=15)

    # Act
    result = await service.sync_user_roles(user.id, mock_provider)

    # Assert
    assert result.outcome is RoleSyncOutcome.SKIPPED_TTL
    mock_provider.get_user_by_user_id.assert_not_awaited()


# ---------------------------------------------------------------------------
# #2531 — an empty provider response must never revoke authority
# ---------------------------------------------------------------------------

OWN_UNIT1_ROLE_RAW = {
    "role": RoleName.CO2_USER_STD.value,
    "on": {"kind": "own", "institutional_id": "unit1"},
}


async def _make_user(db_session, roles_raw: list[dict], last_sync=None) -> User:
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=roles_raw,
        last_roles_sync_at=last_sync,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def _provider_returning(roles: list[Role]) -> AsyncMock:
    provider = AsyncMock()
    provider.get_user_by_user_id = AsyncMock(
        return_value={
            "email": "test@example.com",
            "code": "12345",
            "display_name": "Test User",
            "function": "Tester",
            "roles": roles,
        }
    )
    return provider


@pytest.mark.asyncio
async def test_empty_provider_response_does_not_wipe_existing_roles(db_session):
    """The direct regression for #2531.

    Accred answering "no authorizations" (unconfigured pod, transient blip,
    prefix mismatch) is not the same statement as "this user lost every
    role". Without the guard, ``roles_raw`` was emptied and the user's next
    request 403'd.
    """
    user = await _make_user(
        db_session,
        [OWN_UNIT1_ROLE_RAW],
        last_sync=datetime.now(UTC) - timedelta(hours=1),
    )
    service = RoleSyncService(db_session)

    result = await service.sync_user_roles(user.id, _provider_returning([]))

    assert result.outcome is RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY
    # roles_changed gates sync_user_units, which drops every association
    # when the role set yields no units — it must stay False.
    assert result.roles_changed is False
    assert result.has_changed is False
    await db_session.refresh(user)
    assert user.roles_raw == [OWN_UNIT1_ROLE_RAW]


@pytest.mark.asyncio
async def test_suspicious_empty_leaves_sync_timestamp_untouched(db_session):
    """A refused sync has not succeeded, so it must not be stamped as one —
    otherwise the TTL gate hides the failure for the next 15 minutes.
    """
    stale_stamp = datetime.now(UTC) - timedelta(hours=1)
    user = await _make_user(db_session, [OWN_UNIT1_ROLE_RAW], last_sync=stale_stamp)
    service = RoleSyncService(db_session)

    await service.sync_user_roles(user.id, _provider_returning([]))

    # The next sync really does retry rather than being TTL-gated.
    retry_provider = _provider_returning([])
    await service.sync_user_roles(user.id, retry_provider)
    retry_provider.get_user_by_user_id.assert_awaited_once()

    await db_session.refresh(user)
    assert user.last_roles_sync_at is not None
    # SQLite hands back naive datetimes for DateTime(timezone=True).
    assert user.last_roles_sync_at.replace(tzinfo=UTC) == stale_stamp


@pytest.mark.asyncio
async def test_non_empty_role_change_still_applies(db_session):
    """The guard must not freeze roles: a real, non-empty change persists,
    including a genuine downgrade to fewer roles.
    """
    user = await _make_user(
        db_session,
        [
            OWN_UNIT1_ROLE_RAW,
            {
                "role": RoleName.CO2_SUPERADMIN.value,
                "on": {"kind": "global"},
            },
        ],
        last_sync=datetime.now(UTC) - timedelta(hours=1),
    )
    service = RoleSyncService(db_session)
    new_roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]

    result = await service.sync_user_roles(user.id, _provider_returning(new_roles))

    assert result.outcome is RoleSyncOutcome.APPLIED
    assert result.roles_changed is True
    await db_session.refresh(user)
    assert user.roles == new_roles
    assert user.last_roles_sync_at is not None


@pytest.mark.asyncio
async def test_user_with_no_roles_receiving_no_roles_is_not_an_error(db_session):
    """Empty-in / empty-out is unambiguous: nothing to protect, nothing to
    retry. It must settle as NO_CHANGE with the timestamp stamped, or every
    role-less user would re-hit the provider on every request.
    """
    user = await _make_user(db_session, [], last_sync=None)
    service = RoleSyncService(db_session)

    result = await service.sync_user_roles(user.id, _provider_returning([]))

    assert result.outcome is RoleSyncOutcome.NO_CHANGE
    await db_session.refresh(user)
    assert user.last_roles_sync_at is not None


@pytest.mark.asyncio
async def test_provider_network_error_skips_without_touching_roles(db_session):
    """An unreachable or unconfigured provider aborts the sync as its own
    reportable outcome — no wipe, no timestamp.
    """
    user = await _make_user(db_session, [OWN_UNIT1_ROLE_RAW], last_sync=None)
    provider = AsyncMock()
    provider.get_user_by_user_id = AsyncMock(
        side_effect=RoleProviderNetworkError("Accred API is not configured")
    )
    service = RoleSyncService(db_session)

    result = await service.sync_user_roles(user.id, provider)

    assert result.outcome is RoleSyncOutcome.SKIPPED_PROVIDER_UNAVAILABLE
    assert result.roles_changed is False
    await db_session.refresh(user)
    assert user.roles_raw == [OWN_UNIT1_ROLE_RAW]
    assert user.last_roles_sync_at is None


@pytest.mark.asyncio
async def test_login_stamps_sync_time_so_next_session_call_is_ttl_gated(db_session):
    """Login has just read authoritative roles from the provider.

    Without stamping ``last_roles_sync_at`` the TTL gate is already expired,
    so the very next ``/v1/session`` re-syncs — doubling provider load per
    login and reopening the wipe window seconds after a user recovers.
    """
    user = await UserService(db_session).upsert_user(
        id=None,
        email="fresh-login@example.com",
        institutional_id="12345",
        display_name="Fresh Login",
        provider=UserProvider.ACCRED,
        roles=[Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="unit1"))],
    )
    await db_session.commit()
    assert user.last_roles_sync_at is not None

    provider = _provider_returning([])
    result = await RoleSyncService(db_session).sync_user_roles(user.id, provider)

    assert result.outcome is RoleSyncOutcome.SKIPPED_TTL
    provider.get_user_by_user_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_units_removes_stale_associations(db_session):
    """Test that unit sync removes associations for removed roles."""
    # Arrange
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
    )
    db_session.add(user)
    await db_session.commit()

    # Create units
    unit1 = Unit(
        institutional_code="unit1",
        institutional_id="unit1",
        name="Unit 1",
        provider=UserProvider.ACCRED,
        level=2,
    )
    unit2 = Unit(
        institutional_code="unit2",
        institutional_id="unit2",
        name="Unit 2",
        provider=UserProvider.ACCRED,
        level=2,
    )
    db_session.add_all([unit1, unit2])
    await db_session.commit()

    # Create initial association
    from app.models.unit_user import UnitUser

    unit_user = UnitUser(unit_id=unit1.id, user_id=user.id, role=RoleName.CO2_USER_STD)
    db_session.add(unit_user)
    await db_session.commit()

    # Sync with only unit2 role
    roles = [Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="unit2"))]
    service = RoleSyncService(db_session)
    await service.sync_user_units(user.id, roles)

    # Assert
    from sqlalchemy import select

    result = await db_session.execute(
        select(UnitUser).where(UnitUser.user_id == user.id)
    )
    associations = list(result.all())
    assert len(associations) == 1
    assert associations[0][0].unit_id == unit2.id
