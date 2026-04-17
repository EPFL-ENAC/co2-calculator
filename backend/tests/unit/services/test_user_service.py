"""Tests for UserService.unit_membership_sync_user and upsert_user sync logic."""

import pytest
from fastapi import HTTPException
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


# ---------------------------------------------------------------------------
# Tests for get_uniq_unit_institutional_id_from_roles
# ---------------------------------------------------------------------------


class TestGetUniqUnitInstitutionalIdFromRoles:
    def _svc(self):
        from unittest.mock import MagicMock

        return UserService(MagicMock())

    def test_none_roles(self):
        assert self._svc().get_uniq_unit_institutional_id_from_roles(None) == []

    def test_empty_roles(self):
        assert self._svc().get_uniq_unit_institutional_id_from_roles([]) == []

    def test_extracts_unique_ids(self):
        roles = [
            _role(RoleName.CO2_USER_STD, "CF_A"),
            _role(RoleName.CO2_USER_PRINCIPAL, "CF_A"),
            _role(RoleName.CO2_USER_STD, "CF_B"),
        ]
        result = self._svc().get_uniq_unit_institutional_id_from_roles(roles)
        assert sorted(result) == ["CF_A", "CF_B"]

    def test_skips_roles_without_institutional_id(self):
        role_no_id = Role(role=RoleName.CO2_USER_STD, on=RoleScope())
        result = self._svc().get_uniq_unit_institutional_id_from_roles([role_no_id])
        assert result == []


# ---------------------------------------------------------------------------
# Tests for _build_policy_input
# ---------------------------------------------------------------------------


class TestBuildPolicyInput:
    def _svc(self):
        from unittest.mock import MagicMock

        return UserService(MagicMock())

    def test_builds_correct_structure(self):
        user = User(
            id=1,
            institutional_id="100",
            email="u@test.com",
            provider=UserProvider.TEST,
            roles=[],
        )
        result = self._svc()._build_policy_input(user, "read")
        assert result["action"] == "read"
        assert result["resource_type"] == "user"
        assert result["user"]["id"] == 1
        assert result["user"]["email"] == "u@test.com"
        assert result["user"]["roles"] == []

    def test_none_roles_defaults(self):
        user = User(
            id=2,
            institutional_id="200",
            email="u2@test.com",
            provider=UserProvider.TEST,
            roles=None,
        )
        result = self._svc()._build_policy_input(user, "create")
        assert result["user"]["roles"] == []


# ---------------------------------------------------------------------------
# Tests for _upsert_user_identity
# ---------------------------------------------------------------------------


class TestUpsertUserIdentity:
    async def test_raises_without_provider(self, db_session):
        svc = UserService(db_session)
        with pytest.raises(ValueError, match="Provider is required"):
            await svc._upsert_user_identity(
                id=None,
                institutional_id="123",
                email="test@test.com",
                provider=None,
            )

    async def test_creates_new_user(self, db_session):
        svc = UserService(db_session)
        user = await svc._upsert_user_identity(
            id=None,
            institutional_id="NEW_001",
            email="new@test.com",
            display_name="New",
            provider=UserProvider.TEST,
        )
        assert user.id is not None
        assert user.institutional_id == "NEW_001"

    async def test_updates_existing_user(self, db_session):
        svc = UserService(db_session)
        user1 = await svc._upsert_user_identity(
            id=None,
            institutional_id="UPD_001",
            email="upd@test.com",
            display_name="V1",
            provider=UserProvider.TEST,
        )
        await db_session.commit()

        user2 = await svc._upsert_user_identity(
            id=None,
            institutional_id="UPD_001",
            email="upd@test.com",
            display_name="V2",
            provider=UserProvider.TEST,
        )
        assert user2.id == user1.id
        assert user2.display_name == "V2"

    async def test_provider_mismatch_raises(self, db_session):
        svc = UserService(db_session)
        user = await svc._upsert_user_identity(
            id=None,
            institutional_id="MIS_001",
            email="mis@test.com",
            provider=UserProvider.TEST,
        )
        await db_session.commit()

        with pytest.raises(ValueError, match="provider mismatch"):
            await svc._upsert_user_identity(
                id=user.id,
                institutional_id="MIS_DIFFERENT",
                email="mis2@test.com",
                provider=UserProvider.ACCRED,
            )

    async def test_email_fallback_same_provider(self, db_session):
        svc = UserService(db_session)
        user1 = await svc._upsert_user_identity(
            id=None,
            institutional_id="EMAIL_001",
            email="shared@test.com",
            provider=UserProvider.TEST,
        )
        await db_session.commit()

        # Lookup by different institutional_id but same email+provider → update
        user2 = await svc._upsert_user_identity(
            id=None,
            institutional_id="EMAIL_002",
            email="shared@test.com",
            provider=UserProvider.TEST,
        )
        assert user2.id == user1.id

    async def test_email_fallback_different_provider_uses_different_email(
        self, db_session
    ):
        """Cross-provider with different email creates a new user."""
        svc = UserService(db_session)
        user1 = await svc._upsert_user_identity(
            id=None,
            institutional_id="EP_001",
            email="cross@test.com",
            provider=UserProvider.TEST,
        )
        await db_session.commit()

        # Different provider AND different email → new user
        user2 = await svc._upsert_user_identity(
            id=None,
            institutional_id="EP_002",
            email="cross_accred@test.com",
            provider=UserProvider.ACCRED,
        )
        assert user2.id != user1.id
        assert user2.institutional_id == "EP_002"


# ---------------------------------------------------------------------------
# Tests for list_users (policy-gated)
# ---------------------------------------------------------------------------


class TestListUsers:
    async def test_list_users_denied(self, db_session):
        from unittest.mock import patch

        svc = UserService(db_session)
        user = _make_user()
        db_session.add(user)
        await db_session.flush()

        with patch(
            "app.services.user_service.query_policy",
            return_value={"allow": False, "reason": "no access"},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await svc.list_users(user)
            assert exc_info.value.status_code == 403

    async def test_list_users_allowed(self, db_session):
        from unittest.mock import patch

        svc = UserService(db_session)
        user = _make_user()
        db_session.add(user)
        await db_session.flush()

        with patch(
            "app.services.user_service.query_policy",
            return_value={"allow": True, "filters": {}},
        ):
            result = await svc.list_users(user)
            assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests for get_user (policy-gated)
# ---------------------------------------------------------------------------


class TestGetUser:
    async def test_get_user_not_found(self, db_session):
        svc = UserService(db_session)
        current = _make_user()
        db_session.add(current)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_user(99999, current)
        assert exc_info.value.status_code == 404

    async def test_get_user_denied_returns_404(self, db_session):
        from unittest.mock import patch

        svc = UserService(db_session)
        current = _make_user(institutional_id="CUR", email="cur@test.com")
        target = _make_user(institutional_id="TGT", email="tgt@test.com")
        db_session.add_all([current, target])
        await db_session.flush()

        with patch(
            "app.services.user_service.query_policy",
            return_value={"allow": False},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await svc.get_user(target.id, current)
            assert exc_info.value.status_code == 404

    async def test_get_user_allowed(self, db_session):
        from unittest.mock import patch

        svc = UserService(db_session)
        current = _make_user(institutional_id="CUR2", email="cur2@test.com")
        target = _make_user(institutional_id="TGT2", email="tgt2@test.com")
        db_session.add_all([current, target])
        await db_session.flush()

        with patch(
            "app.services.user_service.query_policy",
            return_value={"allow": True},
        ):
            result = await svc.get_user(target.id, current)
            assert result.id == target.id


# ---------------------------------------------------------------------------
# Tests for CRUD operations
# ---------------------------------------------------------------------------


class TestCrudOperations:
    async def test_create_user(self, db_session):
        svc = UserService(db_session)
        current = _make_user()
        db_session.add(current)
        await db_session.flush()

        user = await svc.create_user(
            {"id": "NEW_CRUD", "email": "crud@test.com", "display_name": "CRUD User"},
            current,
        )
        assert user.id is not None
        assert user.email == "crud@test.com"

    async def test_delete_user(self, db_session):
        svc = UserService(db_session)
        current = _make_user(institutional_id="DEL_CUR", email="delcur@test.com")
        target = _make_user(institutional_id="DEL_TGT", email="deltgt@test.com")
        db_session.add_all([current, target])
        await db_session.flush()

        deleted = await svc.delete_user(target.id, current)
        assert deleted is True

    async def test_delete_nonexistent(self, db_session):
        svc = UserService(db_session)
        current = _make_user()
        db_session.add(current)
        await db_session.flush()

        deleted = await svc.delete_user(99999, current)
        assert deleted is False

    async def test_get_by_id(self, db_session):
        svc = UserService(db_session)
        user = _make_user()
        db_session.add(user)
        await db_session.flush()

        found = await svc.get_by_id(user.id)
        assert found is not None
        assert found.id == user.id

    async def test_get_by_email(self, db_session):
        svc = UserService(db_session)
        user = _make_user(email="unique_lookup@test.com")
        db_session.add(user)
        await db_session.flush()

        found = await svc.get_by_email("unique_lookup@test.com")
        assert found is not None

    async def test_count(self, db_session):
        svc = UserService(db_session)
        user = _make_user()
        db_session.add(user)
        await db_session.flush()

        c = await svc.count()
        assert c >= 1

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
