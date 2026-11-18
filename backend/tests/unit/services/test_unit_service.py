"""Unit tests for unit service."""

import pytest
from fastapi import HTTPException

from app.models.user import GlobalScope, Role, RoleName, UnitScope
from app.services.unit_service import UnitService


class TestGetUserUnitsLevelFilter:
    """Regression tests for #930 — /users/units must return only level-4 units."""

    async def test_get_user_units_returns_only_level_4_when_user_has_mixed_level_roles(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
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
