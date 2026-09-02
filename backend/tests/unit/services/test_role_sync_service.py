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
async def test_suspicious_empty_engages_backoff_for_immediate_retries(db_session):
    """A skip now stamps the timestamp too (#2539) — a near-simultaneous
    second call (e.g. another browser tab) is TTL-gated instead of also
    re-hitting the provider with zero rate limit.
    """
    stale_stamp = datetime.now(UTC) - timedelta(hours=1)
    user = await _make_user(db_session, [OWN_UNIT1_ROLE_RAW], last_sync=stale_stamp)
    service = RoleSyncService(db_session)

    first = await service.sync_user_roles(user.id, _provider_returning([]))
    assert first.outcome is RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY

    retry_provider = _provider_returning([])
    second = await service.sync_user_roles(user.id, retry_provider)

    assert second.outcome is RoleSyncOutcome.SKIPPED_TTL
    retry_provider.get_user_by_user_id.assert_not_awaited()
    await db_session.refresh(user)
    assert user.last_roles_sync_at.replace(tzinfo=UTC) > stale_stamp


@pytest.mark.asyncio
async def test_suspicious_empty_still_retries_once_the_ttl_elapses(db_session):
    """The backoff is one TTL period, not permanent — once it elapses, the
    next call retries against the provider again (#2539).
    """
    user = await _make_user(
        db_session,
        [OWN_UNIT1_ROLE_RAW],
        last_sync=datetime.now(UTC) - timedelta(hours=1),
    )
    service = RoleSyncService(db_session)
    await service.sync_user_roles(user.id, _provider_returning([]))

    # Simulate the TTL period having elapsed since the backoff stamp. Mutate
    # the same in-memory object rather than refresh()-ing it — SQLite hands
    # back naive datetimes on an explicit reload, which is a test-harness
    # quirk (Postgres in prod preserves tz), not something worth guarding in
    # the service for.
    user.last_roles_sync_at = datetime.now(UTC) - timedelta(minutes=20)
    await db_session.commit()

    retry_provider = _provider_returning([])
    result = await service.sync_user_roles(user.id, retry_provider)

    assert result.outcome is RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY
    retry_provider.get_user_by_user_id.assert_awaited_once()


# ---------------------------------------------------------------------------
# #2539 — two-strikes: a lone empty response never revokes, a confirmed
# second one (after 2x the sync TTL) does.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_strike_records_when_it_started_without_wiping(db_session):
    user = await _make_user(
        db_session,
        [OWN_UNIT1_ROLE_RAW],
        last_sync=datetime.now(UTC) - timedelta(hours=1),
    )
    service = RoleSyncService(db_session)

    result = await service.sync_user_roles(user.id, _provider_returning([]))

    assert result.outcome is RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY
    await db_session.refresh(user)
    assert user.roles_raw == [OWN_UNIT1_ROLE_RAW]
    assert user.roles_empty_since is not None


@pytest.mark.asyncio
async def test_second_strike_within_the_window_still_does_not_wipe(db_session):
    """Strike two, but not yet 2x TTL after strike one: still a blip."""
    user = await _make_user(
        db_session,
        [OWN_UNIT1_ROLE_RAW],
        last_sync=datetime.now(UTC) - timedelta(hours=1),
    )
    service = RoleSyncService(db_session, sync_ttl_minutes=15)
    first_seen = datetime.now(UTC) - timedelta(minutes=20)  # < 2x15min
    user.roles_empty_since = first_seen
    await db_session.commit()

    result = await service.sync_user_roles(user.id, _provider_returning([]))

    assert result.outcome is RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY
    await db_session.refresh(user)
    assert user.roles_raw == [OWN_UNIT1_ROLE_RAW]
    # The original first-seen time stands — a second poke doesn't restart it.
    assert user.roles_empty_since.replace(tzinfo=UTC) == first_seen


@pytest.mark.asyncio
async def test_second_strike_past_the_window_applies_the_revocation(db_session):
    """Confirmed twice, 2x TTL apart: this is what a real revocation looks
    like, so it applies for real — the only path that can revoke without
    a login (#2539).
    """
    user = await _make_user(
        db_session,
        [OWN_UNIT1_ROLE_RAW],
        last_sync=datetime.now(UTC) - timedelta(hours=1),
    )
    service = RoleSyncService(db_session, sync_ttl_minutes=15)
    user.roles_empty_since = datetime.now(UTC) - timedelta(minutes=31)  # >= 2x15min
    await db_session.commit()

    result = await service.sync_user_roles(user.id, _provider_returning([]))

    assert result.outcome is RoleSyncOutcome.APPLIED
    assert result.roles_changed is True
    await db_session.refresh(user)
    assert user.roles_raw == []
    assert user.roles_empty_since is None


@pytest.mark.asyncio
async def test_recovering_to_the_same_roles_clears_a_pending_strike(db_session):
    """A matching non-empty result also confirms the provider is answering —
    a stale first-seen time must not survive to poison a later, unrelated
    empty response (#2539).
    """
    user = await _make_user(
        db_session,
        [OWN_UNIT1_ROLE_RAW],
        last_sync=datetime.now(UTC) - timedelta(hours=1),
    )
    service = RoleSyncService(db_session)
    user.roles_empty_since = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    result = await service.sync_user_roles(
        user.id, _provider_returning([Role(**OWN_UNIT1_ROLE_RAW)])
    )

    assert result.outcome is RoleSyncOutcome.NO_CHANGE
    await db_session.refresh(user)
    assert user.roles_empty_since is None


@pytest.mark.asyncio
async def test_force_bypasses_the_guard_for_admin_revoke(db_session):
    """The admin-revoke endpoint's whole mechanism (#2539): force=True skips
    both the TTL gate and the suspicious-empty guard, so a single fresh
    Accred check that comes back empty applies immediately — no two-strikes
    wait, since a human already confirmed the intent.
    """
    user = await _make_user(
        db_session, [OWN_UNIT1_ROLE_RAW], last_sync=datetime.now(UTC)
    )
    service = RoleSyncService(db_session)

    result = await service.sync_user_roles(user.id, _provider_returning([]), force=True)

    assert result.outcome is RoleSyncOutcome.APPLIED
    await db_session.refresh(user)
    assert user.roles_raw == []


@pytest.mark.asyncio
async def test_force_does_not_revoke_when_accred_still_reports_roles(db_session):
    """Force only bypasses the guard — it never invents a revocation Accred
    doesn't back. If Accred still returns the user's roles, nothing changes.
    """
    user = await _make_user(
        db_session, [OWN_UNIT1_ROLE_RAW], last_sync=datetime.now(UTC)
    )
    service = RoleSyncService(db_session)

    result = await service.sync_user_roles(
        user.id,
        _provider_returning([Role(**OWN_UNIT1_ROLE_RAW)]),
        force=True,
    )

    assert result.outcome is RoleSyncOutcome.NO_CHANGE
    await db_session.refresh(user)
    assert user.roles_raw == [OWN_UNIT1_ROLE_RAW]


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
    reportable outcome — no wipe. The timestamp IS stamped (#2539 backoff):
    a burst of near-simultaneous calls during an outage shouldn't all
    re-hit the provider with zero rate limit.
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
    assert user.last_roles_sync_at is not None


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
