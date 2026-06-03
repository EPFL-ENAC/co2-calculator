"""Tests for SQL-level backoffice scoping predicates."""

from sqlmodel import select

from app.models.unit import Unit
from app.utils.scoping import build_scope_subtree_predicate


async def _enac_subtree(db_session, make_unit):
    anchor = await make_unit(
        db_session,
        institutional_code="12635",
        institutional_id="13030",
        name="ENAC",
        level=2,
        path_institutional_code="10582 12635",
    )
    child = await make_unit(
        db_session,
        institutional_code="11435",
        institutional_id="13031",
        name="ENAC-SG",
        level=3,
        path_institutional_code="10582 12635 11435",
    )
    leaf = await make_unit(
        db_session,
        institutional_code="14270",
        institutional_id="13032",
        name="ENAC-IT4R",
        level=4,
        path_institutional_code="10582 12635 11435 14270",
    )
    outside = await make_unit(
        db_session,
        institutional_code="99999",
        institutional_id="88888",
        name="OUTSIDE",
        level=2,
        path_institutional_code="10582 99999",
    )
    return anchor, child, leaf, outside


class TestBuildScopeSubtreePredicate:
    async def test_matches_anchor_and_descendants_only(self, db_session, make_unit):
        anchor, child, leaf, outside = await _enac_subtree(db_session, make_unit)
        stmt = select(Unit).where(build_scope_subtree_predicate({"13030"}))
        rows = (await db_session.exec(stmt)).all()
        names = {u.name for u in rows}
        assert names == {"ENAC", "ENAC-SG", "ENAC-IT4R"}
        assert "OUTSIDE" not in names

    async def test_composes_with_level_filter_for_dropdown(self, db_session, make_unit):
        await _enac_subtree(db_session, make_unit)
        # The /affiliations dropdown shows lvl2/3 within the scope subtree.
        stmt = (
            select(Unit)
            .where(build_scope_subtree_predicate({"13030"}))
            .where(Unit.level.in_([2, 3]))  # type: ignore[attr-defined]
        )
        names = {u.name for u in (await db_session.exec(stmt)).all()}
        assert names == {"ENAC", "ENAC-SG"}
