"""Tests for UserService.unit_membership_sync_user and upsert_user sync logic."""

import pytest
from sqlmodel import select

from app.models.unit import Unit
from app.models.unit_user import UnitUser
from app.models.user import (
    Role,
    RoleName,
    RoleScope,
    User,
    UserProvider,
)
from app.services.user_service import UserService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides) -> User:
    defaults = dict(
        institutional_id="100000",
        email="test@example.com",
        provider=UserProvider.TEST,
        display_name="Test User",
    )
    defaults.update(overrides)
    return User(**defaults)


def _make_unit(institutional_id: str, institutional_code: str, **overrides) -> Unit:
    defaults = dict(
        institutional_id=institutional_id,
        institutional_code=institutional_code,
        name=f"Unit-{institutional_code}",
        level=2,
        provider=UserProvider.TEST,
    )
    defaults.update(overrides)
    return Unit(**defaults)


def _role(role_name: RoleName, institutional_id: str) -> Role:
    return Role(role=role_name, on=RoleScope(institutional_id=institutional_id))


async def _get_unit_users(session, user_id: int) -> list[UnitUser]:
    result = await session.exec(select(UnitUser).where(UnitUser.user_id == user_id))
    return list(result.all())


# ---------------------------------------------------------------------------
# Tests for unit_membership_sync_user
# ---------------------------------------------------------------------------


class TestUnitMembershipSyncUser:
    """Tests for the unit_membership_sync_user method."""

    async def test_creates_associations_for_matching_roles(self, db_session):
        """Happy path: user with 2 unit-scoped roles gets 2 unit_users rows."""
        user = _make_user()
        unit_a = _make_unit("CF_A", "CODE_A")
        unit_b = _make_unit("CF_B", "CODE_B")
        db_session.add_all([user, unit_a, unit_b])
        await db_session.flush()

        roles = [
            _role(RoleName.CO2_USER_STD, "CF_A"),
            _role(RoleName.CO2_USER_PRINCIPAL, "CF_B"),
        ]

        svc = UserService(db_session)
        await svc.unit_membership_sync_user(
            user=user, roles=roles, units=[unit_a, unit_b]
        )

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 2

        by_unit = {r.unit_id: r for r in rows}
        assert by_unit[unit_a.id].role == RoleName.CO2_USER_STD
        assert by_unit[unit_b.id].role == RoleName.CO2_USER_PRINCIPAL

    async def test_removes_stale_associations(self, db_session):
        """User had 2 units, now has 1 — the old association is deleted."""
        user = _make_user()
        unit_a = _make_unit("CF_A", "CODE_A")
        unit_b = _make_unit("CF_B", "CODE_B")
        db_session.add_all([user, unit_a, unit_b])
        await db_session.flush()

        # Seed an existing association for unit_b
        db_session.add(
            UnitUser(unit_id=unit_b.id, user_id=user.id, role=RoleName.CO2_USER_STD)
        )
        await db_session.flush()

        # Now sync with only unit_a in roles
        roles = [_role(RoleName.CO2_USER_STD, "CF_A")]
        svc = UserService(db_session)
        await svc.unit_membership_sync_user(user=user, roles=roles, units=[unit_a])

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 1
        assert rows[0].unit_id == unit_a.id

    async def test_no_roles_deletes_all_associations(self, db_session):
        """User has no matching roles — all associations are deleted."""
        user = _make_user()
        unit_a = _make_unit("CF_A", "CODE_A")
        db_session.add_all([user, unit_a])
        await db_session.flush()

        # Seed existing association
        db_session.add(
            UnitUser(unit_id=unit_a.id, user_id=user.id, role=RoleName.CO2_USER_STD)
        )
        await db_session.flush()

        svc = UserService(db_session)
        await svc.unit_membership_sync_user(user=user, roles=[], units=[])

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 0

    async def test_role_upgrade(self, db_session):
        """User was CO2_USER_STD on a unit, now CO2_USER_PRINCIPAL — role is updated."""
        user = _make_user()
        unit_a = _make_unit("CF_A", "CODE_A")
        db_session.add_all([user, unit_a])
        await db_session.flush()

        # Seed existing association with STD role
        db_session.add(
            UnitUser(unit_id=unit_a.id, user_id=user.id, role=RoleName.CO2_USER_STD)
        )
        await db_session.flush()

        roles = [_role(RoleName.CO2_USER_PRINCIPAL, "CF_A")]
        svc = UserService(db_session)
        await svc.unit_membership_sync_user(user=user, roles=roles, units=[unit_a])

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 1
        assert rows[0].role == RoleName.CO2_USER_PRINCIPAL

    async def test_unknown_unit_institutional_id_skipped(self, db_session):
        """Unit whose institutional_id doesn't match any role is skipped gracefully."""
        user = _make_user()
        unit_a = _make_unit("CF_A", "CODE_A")
        unit_orphan = _make_unit("CF_ORPHAN", "CODE_ORPHAN")
        db_session.add_all([user, unit_a, unit_orphan])
        await db_session.flush()

        # Roles only reference CF_A — CF_ORPHAN should be skipped
        roles = [_role(RoleName.CO2_USER_STD, "CF_A")]
        svc = UserService(db_session)
        await svc.unit_membership_sync_user(
            user=user, roles=roles, units=[unit_a, unit_orphan]
        )

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 1
        assert rows[0].unit_id == unit_a.id

    async def test_picks_highest_priority_role(self, db_session):
        """When user has multiple roles on same unit, highest priority wins."""
        user = _make_user()
        unit_a = _make_unit("CF_A", "CODE_A")
        db_session.add_all([user, unit_a])
        await db_session.flush()

        roles = [
            _role(RoleName.CO2_USER_STD, "CF_A"),
            _role(RoleName.CO2_USER_PRINCIPAL, "CF_A"),
        ]
        svc = UserService(db_session)
        await svc.unit_membership_sync_user(user=user, roles=roles, units=[unit_a])

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 1
        assert rows[0].role == RoleName.CO2_USER_PRINCIPAL

    async def test_raises_on_null_user_id(self, db_session):
        """Raises ValueError if user.id is None."""
        user = User(
            institutional_id="999",
            email="none@example.com",
            provider=UserProvider.TEST,
        )
        # Don't flush — id stays None
        svc = UserService(db_session)
        with pytest.raises(ValueError, match="valid ID"):
            await svc.unit_membership_sync_user(user=user, roles=[], units=[])

    async def test_does_not_affect_other_users(self, db_session):
        """Syncing user A should not touch user B's associations."""
        user_a = _make_user(institutional_id="A", email="a@example.com")
        user_b = _make_user(institutional_id="B", email="b@example.com")
        unit = _make_unit("CF_X", "CODE_X")
        db_session.add_all([user_a, user_b, unit])
        await db_session.flush()

        # Give user_b an association
        db_session.add(
            UnitUser(unit_id=unit.id, user_id=user_b.id, role=RoleName.CO2_USER_STD)
        )
        await db_session.flush()

        # Sync user_a with no units
        svc = UserService(db_session)
        await svc.unit_membership_sync_user(user=user_a, roles=[], units=[])

        # user_b's association should be untouched
        rows_b = await _get_unit_users(db_session, user_b.id)
        assert len(rows_b) == 1


# ---------------------------------------------------------------------------
# Tests for upsert_user (integration of the full sync flow)
# ---------------------------------------------------------------------------


class TestUpsertUserSync:
    """Tests for the unit sync flow within upsert_user."""

    async def test_upsert_user_resolves_units_and_creates_associations(
        self, db_session
    ):
        """upsert_user resolves institutional_ids to unit.ids
        and creates associations."""
        unit_a = _make_unit("CF_A", "CODE_A")
        db_session.add(unit_a)
        await db_session.flush()

        roles = [_role(RoleName.CO2_USER_STD, "CF_A")]

        svc = UserService(db_session)
        user = await svc.upsert_user(
            id=None,
            email="new@example.com",
            institutional_id="200000",
            display_name="New User",
            roles=roles,
            provider=UserProvider.TEST,
        )

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 1
        assert rows[0].unit_id == unit_a.id
        assert rows[0].role == RoleName.CO2_USER_STD

    async def test_upsert_user_cleans_stale_on_role_change(self, db_session):
        """When roles change between upserts, old associations are cleaned up."""
        unit_a = _make_unit("CF_A", "CODE_A")
        unit_b = _make_unit("CF_B", "CODE_B")
        db_session.add_all([unit_a, unit_b])
        await db_session.flush()

        svc = UserService(db_session)

        # First upsert — roles on both units
        roles_v1 = [
            _role(RoleName.CO2_USER_STD, "CF_A"),
            _role(RoleName.CO2_USER_STD, "CF_B"),
        ]
        user = await svc.upsert_user(
            id=None,
            email="change@example.com",
            institutional_id="300000",
            roles=roles_v1,
            provider=UserProvider.TEST,
        )
        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 2

        # Second upsert — role removed from unit_b
        roles_v2 = [_role(RoleName.CO2_USER_PRINCIPAL, "CF_A")]
        user = await svc.upsert_user(
            id=user.id,
            email="change@example.com",
            institutional_id="300000",
            roles=roles_v2,
            provider=UserProvider.TEST,
        )
        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 1
        assert rows[0].unit_id == unit_a.id
        assert rows[0].role == RoleName.CO2_USER_PRINCIPAL

    async def test_upsert_user_no_unit_roles_clears_all(self, db_session):
        """User with no unit-scoped roles gets all associations cleared."""
        unit_a = _make_unit("CF_A", "CODE_A")
        db_session.add(unit_a)
        await db_session.flush()

        svc = UserService(db_session)

        # First upsert with a role
        roles_v1 = [_role(RoleName.CO2_USER_STD, "CF_A")]
        user = await svc.upsert_user(
            id=None,
            email="clear@example.com",
            institutional_id="400000",
            roles=roles_v1,
            provider=UserProvider.TEST,
        )
        assert len(await _get_unit_users(db_session, user.id)) == 1

        # Second upsert with no unit-scoped roles
        user = await svc.upsert_user(
            id=user.id,
            email="clear@example.com",
            institutional_id="400000",
            roles=[],
            provider=UserProvider.TEST,
        )
        assert len(await _get_unit_users(db_session, user.id)) == 0

    async def test_upsert_user_unknown_institutional_id_clears_associations(
        self, db_session
    ):
        """Roles reference an institutional_id not in the DB — associations cleared."""
        svc = UserService(db_session)

        roles = [_role(RoleName.CO2_USER_STD, "CF_NONEXISTENT")]
        user = await svc.upsert_user(
            id=None,
            email="ghost@example.com",
            institutional_id="500000",
            roles=roles,
            provider=UserProvider.TEST,
        )

        rows = await _get_unit_users(db_session, user.id)
        assert len(rows) == 0
