"""Unit tests for RoleSyncService."""

from datetime import datetime, timedelta

import pytest

from app.models.unit import Unit
from app.models.user import Role, RoleName, RoleScope, User, UserProvider
from app.services.role_sync_service import RoleSyncService


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
            {"role": RoleName.CO2_USER_STD.value, "on": {"institutional_id": "unit1"}}
        ],
        last_roles_sync_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    provider_user = {
        "email": "test@example.com",
        "code": "12345",
        "display_name": "Test User",
        "function": "Tester",
        "roles": [
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="unit2"))
        ],
    }

    service = RoleSyncService(db_session)

    # Act
    result = await service.sync_user_roles(user.id, provider_user)

    # Assert
    assert result.has_changed is True
    assert result.roles_changed is True
    user_updated = await service.user_repo.get_by_id(user.id)
    assert user_updated.last_roles_sync_at is not None


@pytest.mark.asyncio
async def test_sync_roles_no_changes(db_session):
    """Test that sync skips update when roles unchanged."""
    # Arrange
    roles_raw = [
        {"role": RoleName.CO2_USER_STD.value, "on": {"institutional_id": "unit1"}}
    ]
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=roles_raw,
        last_roles_sync_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    provider_user = {
        "email": "test@example.com",
        "code": "12345",
        "display_name": "Test User",
        "function": "Tester",
        "roles": [
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="unit1"))
        ],
    }

    service = RoleSyncService(db_session)

    # Act
    result = await service.sync_user_roles(user.id, provider_user)

    # Assert
    assert result.has_changed is False
    assert result.roles_changed is False


@pytest.mark.asyncio
async def test_sync_roles_ignores_recent_sync(db_session):
    """Test that sync respects TTL and skips recent syncs."""
    # Arrange
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=[
            {"role": RoleName.CO2_USER_STD.value, "on": {"institutional_id": "unit1"}}
        ],
        last_roles_sync_at=datetime.utcnow(),  # Just synced
    )
    db_session.add(user)
    await db_session.commit()

    service = RoleSyncService(db_session, sync_ttl_minutes=15)

    # Act
    result = await service.sync_user_roles(user.id, {})

    # Assert
    assert result.skipped_due_to_ttl is True


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
    )
    unit2 = Unit(
        institutional_code="unit2",
        institutional_id="unit2",
        name="Unit 2",
        provider=UserProvider.ACCRED,
    )
    db_session.add_all([unit1, unit2])
    await db_session.commit()

    # Create initial association
    from app.models.unit_user import UnitUser

    unit_user = UnitUser(unit_id=unit1.id, user_id=user.id, role=RoleName.CO2_USER_STD)
    db_session.add(unit_user)
    await db_session.commit()

    # Sync with only unit2 role
    roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="unit2"))]
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
