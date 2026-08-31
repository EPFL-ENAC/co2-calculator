"""Unit tests for unit service."""

import pytest
from fastapi import HTTPException

from app.models.user import GlobalScope, Role, RoleName, UnitScope, User
from app.services.unit_service import UnitService


@pytest.fixture
def mock_unit_service_policy_allow(monkeypatch):
    """Patch query_policy as imported by unit_service (no filters, allow)."""

    async def _mock(*args, **kwargs):
        return {"allow": True, "filters": {}}

    monkeypatch.setattr("app.services.unit_service.query_policy", _mock)
    return _mock


class TestGetUserUnitsLevelFilter:
    """Regression tests for #930 — /users/units must return only level-4 units."""

    async def test_get_user_units_returns_only_level_4_when_user_has_mixed_level_roles(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
        mock_unit_service_policy_allow,
    ):
        """User holding roles across levels 2, 3, 4 sees only the level-4 unit."""
        user = await make_user(db_session)
        unit_l2 = await make_unit(db_session, level=2, name="Faculty")
        unit_l3 = await make_unit(db_session, level=3, name="Institute")
        unit_l4 = await make_unit(db_session, level=4, name="Lab")
        for unit in (unit_l2, unit_l3, unit_l4):
            await make_unit_user(
                db_session,
                unit_id=unit.id,
                user_id=user.id,
                role=RoleName.CO2_USER_PRINCIPAL,
            )

        service = UnitService(session=db_session)
        result = await service.get_user_units(user)

        assert [row["name"] for row in result] == ["Lab"]

    async def test_get_user_units_returns_empty_when_user_only_has_non_level_4_roles(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
        mock_unit_service_policy_allow,
    ):
        """User with only level-3 roles → empty list (filter excludes everything)."""
        user = await make_user(db_session)
        unit_l3 = await make_unit(db_session, level=3, name="Institute")
        await make_unit_user(
            db_session,
            unit_id=unit_l3.id,
            user_id=user.id,
            role=RoleName.CO2_USER_PRINCIPAL,
        )

        service = UnitService(session=db_session)
        result = await service.get_user_units(user)

        assert result == []

    async def test_get_user_units_unchanged_for_user_with_only_level_4_roles(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
        mock_unit_service_policy_allow,
    ):
        """Baseline: level-4-only users see all their labs (no regression)."""
        user = await make_user(db_session)
        lab_a = await make_unit(db_session, level=4, name="LabA")
        lab_b = await make_unit(db_session, level=4, name="LabB")
        for lab in (lab_a, lab_b):
            await make_unit_user(
                db_session,
                unit_id=lab.id,
                user_id=user.id,
                role=RoleName.CO2_USER_PRINCIPAL,
            )

        service = UnitService(session=db_session)
        result = await service.get_user_units(user)

        assert sorted(row["name"] for row in result) == ["LabA", "LabB"]


class TestBuildPolicyInput:
    """Tests for _build_policy_input method."""

    def test_build_policy_input_without_unit(self):
        """Test building policy input without unit context."""
        user = User(
            id="test-user",
            email="test@example.com",
            display_name="Test User",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]

        service = UnitService(session=None)
        input_data = service._build_policy_input(user, "read")

        assert input_data["action"] == "read"
        assert input_data["resource_type"] == "unit"
        assert input_data["user"]["id"] == "test-user"
        assert input_data["user"]["email"] == "test@example.com"
        assert len(input_data["user"]["roles"]) == 1
        assert "resource" not in input_data

    def test_build_policy_input_different_actions(self):
        """Test building policy input for different actions."""
        user = User(
            id="test-user",
            email="test@example.com",
            display_name="Test User",
            provider="test",
        )

        service = UnitService(session=None)

        for action in ["read", "create", "update", "delete"]:
            input_data = service._build_policy_input(user, action)
            assert input_data["action"] == action

    def test_build_policy_input_user_without_roles(self):
        """Test building policy input for user without roles."""
        user = User(
            id="test-user",
            email="test@example.com",
            display_name="Test User",
            provider="test",
        )
        user.roles = []

        service = UnitService(session=None)
        input_data = service._build_policy_input(user, "read")

        assert input_data["user"]["roles"] == []


class TestGetByIdReadPolicy:
    """Regression tests for #2379 — GET /units/{id} must enforce a real read
    policy instead of the legacy allow-all stub.

    The stub made the workspace guard's unit probe (#2369) authorize nothing:
    any authenticated user got 200 for any unit id, and refusals surfaced one
    call later at the workspace boundary — the #2570 incident. get_by_id now
    delegates to require_unit_access, the workspace boundary's own enforcer,
    so probe and workspace call cannot drift.
    """

    async def test_non_member_without_global_scope_is_refused(
        self, db_session, make_unit, make_user
    ):
        """The #2570 trace shape: an existing unit, a user whose roles are
        scoped elsewhere — 403, where the allow-all stub returned 200.
        """
        unit = await make_unit(db_session, level=4, institutional_id="CF-TARGET")
        user = await make_user(db_session)
        user.roles = [
            Role(
                role=RoleName.CO2_USER_PRINCIPAL,
                on=UnitScope(institutional_id="CF-ELSEWHERE"),
            )
        ]

        with pytest.raises(HTTPException) as exc:
            await UnitService(session=db_session).get_by_id(unit.id, user)

        assert exc.value.status_code == 403

    async def test_member_by_unit_scoped_role_reads_the_unit(
        self, db_session, make_unit, make_user
    ):
        unit = await make_unit(db_session, level=4, institutional_id="CF-MINE")
        user = await make_user(db_session)
        user.roles = [
            Role(role=RoleName.CO2_USER_STD, on=UnitScope(institutional_id="CF-MINE"))
        ]

        result = await UnitService(session=db_session).get_by_id(unit.id, user)

        assert result.id == unit.id

    async def test_global_scope_reads_a_unit_without_any_membership(
        self, db_session, make_unit, make_user
    ):
        """#2369's acceptance criterion: a superadmin opens any unit."""
        unit = await make_unit(db_session, level=4, institutional_id="CF-OTHER")
        user = await make_user(db_session)
        user.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]

        result = await UnitService(session=db_session).get_by_id(unit.id, user)

        assert result.id == unit.id

    async def test_global_scope_still_gets_404_for_a_missing_id(
        self, db_session, make_user
    ):
        """require_unit_access lets global scope through before its own None
        check — the explicit 404 ahead of it is load-bearing, not decor.
        """
        user = await make_user(db_session)
        user.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]

        with pytest.raises(HTTPException) as exc:
            await UnitService(session=db_session).get_by_id(999_999, user)

        assert exc.value.status_code == 404


class TestGetUserUnitsNoTruncation:
    """Regression test for #2379 part 2 — the membership list came back capped
    at limit=100, silently truncating the session bootstrap and the stats
    accessible-unit filter for users with more memberships.
    """

    async def test_a_user_with_101_memberships_gets_all_of_them(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
        mock_unit_service_policy_allow,
    ):
        user = await make_user(db_session)
        for _ in range(101):
            unit = await make_unit(db_session, level=4)
            await make_unit_user(
                db_session,
                unit_id=unit.id,
                user_id=user.id,
                role=RoleName.CO2_USER_STD,
            )

        result = await UnitService(session=db_session).get_user_units(user)

        assert len(result) == 101
