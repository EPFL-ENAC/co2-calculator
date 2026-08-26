"""Tests for FactorRepository."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import taxonomy_cache_broadcast as taxonomy_cache_broadcast_mod
from app.core.factor_taxonomy_cache import taxonomy_cache
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.modules.emissions import EmissionType
from app.repositories import factor_repo as factor_repo_mod
from app.repositories.factor_repo import FactorRepository


@pytest.fixture
def repo(monkeypatch):
    """FactorRepository over a bare MagicMock session.

    For tests that only care about query construction / return values.
    Taxonomy-cache invalidation now hooks real SQLAlchemy session
    events (commit-gated, #2258) and can't run against a mock session —
    stubbed out here so it stays a no-op; the dedicated section below
    exercises the real thing against the real ``db_session`` fixture.
    """
    session = MagicMock()
    monkeypatch.setattr(
        factor_repo_mod, "schedule_taxonomy_cache_invalidation", AsyncMock()
    )
    return FactorRepository(session)


@pytest.fixture(autouse=True)
def _clear_taxonomy_cache():
    taxonomy_cache.clear()
    yield
    taxonomy_cache.clear()


@pytest.mark.asyncio
async def test_get(repo):
    factor = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get(1)

    assert result == factor
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_create(repo):
    factor = Factor(
        emission_type_id=EmissionType.food,
        data_entry_type_id=DataEntryTypeEnum.member,
        classification={},
        values={},
    )
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.create(factor)

    assert result == factor
    repo.session.add.assert_called_once_with(factor)
    repo.session.flush.assert_awaited_once()
    repo.session.refresh.assert_awaited_once_with(factor)


@pytest.mark.asyncio
async def test_bulk_create(repo):
    factors = [
        Factor(
            emission_type_id=EmissionType.food,
            data_entry_type_id=DataEntryTypeEnum.member,
            classification={},
            values={},
        )
        for _ in range(3)
    ]
    repo.session.add_all = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.bulk_create(factors)

    assert result == factors
    repo.session.add_all.assert_called_once_with(factors)
    repo.session.flush.assert_awaited_once()
    assert repo.session.refresh.await_count == 3


@pytest.mark.asyncio
async def test_update(repo):
    factor = SimpleNamespace(id=1, name="old")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.update(1, {"name": "new"})

    assert result == factor
    assert factor.name == "new"
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_not_found(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.update(999, {"name": "new"})

    assert result is None


@pytest.mark.asyncio
async def test_delete(repo):
    factor = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.delete = AsyncMock()
    repo.session.flush = AsyncMock()

    result = await repo.delete(1)

    assert result is True
    repo.session.delete.assert_awaited_once_with(factor)


@pytest.mark.asyncio
async def test_delete_not_found(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.delete(999)

    assert result is False


@pytest.mark.asyncio
async def test_list_by_data_entry_type(repo):
    factors = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    result_mock = MagicMock()
    result_mock.all.return_value = factors
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.list_by_data_entry_type(DataEntryTypeEnum.member)

    assert result == factors
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_class_subclass_map(repo):
    factors = [
        ("ClassA", "SubA1"),
        ("ClassA", "SubA2"),
        ("ClassB", "SubB1"),
        ("ClassA", "SubA1"),  # Duplicate
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = factors
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_class_subclass_map(
        DataEntryTypeEnum.scientific,
        kind_field="kind",
        subkind_field="subkind",
        year=2025,
    )

    assert result == {"ClassA": ["SubA1", "SubA2"], "ClassB": ["SubB1"]}


@pytest.mark.asyncio
async def test_get_by_classification_with_subkind(repo):
    factor = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_classification(
        DataEntryTypeEnum.member, kind="k1", subkind="s1", year=2025
    )

    assert result == factor
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_classification_fallback_to_kind_only(repo):
    factor = SimpleNamespace(id=1)
    result_mock_none = MagicMock()
    result_mock_none.one_or_none.return_value = None
    result_mock_factor = MagicMock()
    result_mock_factor.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(side_effect=[result_mock_none, result_mock_factor])

    result = await repo.get_by_classification(
        DataEntryTypeEnum.member, kind="k1", subkind="s1", year=2025
    )

    assert result == factor
    assert repo.session.exec.await_count == 2


@pytest.mark.asyncio
async def test_get_factors_with_fallback(repo):
    factor = SimpleNamespace(id=1)
    result_mock_none = MagicMock()
    result_mock_none.all.return_value = []
    result_mock_factor = MagicMock()
    result_mock_factor.all.return_value = [factor]
    repo.session.exec = AsyncMock(side_effect=[result_mock_none, result_mock_factor])

    result = await repo.get_factors(
        DataEntryTypeEnum.train,
        fallbacks={"country_code": "RoW"},
        kind="train",
        country_code="FR",
    )

    assert result == [factor]
    assert repo.session.exec.await_count == 2


# ======================================================================
# get_by_classification — kind_field_override guard
# ======================================================================


def _override_handler() -> MagicMock:
    """A handler mock that declares kind_field_override (purchase-style)."""
    h = MagicMock()
    h.kind_field = "purchase_institutional_code"
    h.subkind_field = ""
    h.kind_field_override = "purchase_additional_code"
    return h


@pytest.mark.asyncio
async def test_get_by_classification_override_handler_no_subkind(repo):
    """Handler with kind_field_override, no subkind supplied → single exec
    call that targets only 'average' rows (override key absent).
    """
    factor = SimpleNamespace(id=42)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)

    with patch("app.repositories.factor_repo.BaseModuleHandler") as mock_cls:
        mock_cls.get_by_type.return_value = _override_handler()
        result = await repo.get_by_classification(
            DataEntryTypeEnum.consumable_accessories,
            kind="FOOD",
            year=2025,
        )

    assert result is factor
    assert repo.session.exec.await_count == 1


@pytest.mark.asyncio
async def test_get_by_classification_override_handler_subkind_miss_fallback(repo):
    """Handler with kind_field_override, subkind supplied but first query
    misses → falls back to kind-only query; both queries should include
    the override-null guard.
    """
    factor = SimpleNamespace(id=43)
    result_miss = MagicMock()
    result_miss.one_or_none.return_value = None
    result_hit = MagicMock()
    result_hit.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(side_effect=[result_miss, result_hit])

    with patch("app.repositories.factor_repo.BaseModuleHandler") as mock_cls:
        mock_cls.get_by_type.return_value = _override_handler()
        result = await repo.get_by_classification(
            DataEntryTypeEnum.consumable_accessories,
            kind="FOOD",
            subkind="sub1",
            year=2025,
        )

    assert result is factor
    assert repo.session.exec.await_count == 2


@pytest.mark.asyncio
async def test_get_by_classification_override_handler_sql_includes_override_null(repo):
    """The WHERE clause for an override-handler query must include an IS NULL
    condition on the override field.

    This prevents MultipleResultsFound when several factors share the same
    kind value but carry different override codes — without this guard,
    one_or_none() raises on the second (or more) matching rows.
    """
    from sqlalchemy.dialects.postgresql import dialect as pg_dialect

    captured: list = []

    async def capturing_exec(stmt):
        captured.append(stmt)
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        return mock_result

    repo.session.exec = capturing_exec

    with patch("app.repositories.factor_repo.BaseModuleHandler") as mock_cls:
        mock_cls.get_by_type.return_value = _override_handler()
        await repo.get_by_classification(
            DataEntryTypeEnum.consumable_accessories,
            kind="FOOD",
            year=2025,
        )

    assert len(captured) == 1
    sql = str(
        captured[0].compile(
            dialect=pg_dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    # The compiled SQL must contain the override field null guard so that only
    # "average" rows (those without purchase_additional_code) are eligible.
    assert "purchase_additional_code" in sql
    assert "IS NULL" in sql.upper()


# ======================================================================
# #2050 J4 — one query for a whole emission subtree
# ======================================================================


@pytest.mark.asyncio
async def test_list_by_emission_types_returns_all_types_in_one_query(db_session):
    """Strategy B3 used to loop ``get_subtree_leaves`` and issue one
    ``list_by_emission_type`` query per leaf — 24 queries for a single
    headcount member POST (#2050 J4). This is the set-based replacement.
    """
    repo = FactorRepository(db_session)
    wanted = [EmissionType.food__vegetarian, EmissionType.commuting__cycling]
    for emission_type in [*wanted, EmissionType.waste__incineration]:
        db_session.add(
            Factor(
                emission_type_id=emission_type.value,
                data_entry_type_id=DataEntryTypeEnum.member.value,
                classification={},
                values={"ef_kg_co2eq_per_unit": 1.0},
                year=2025,
            )
        )
    # Same emission type, wrong year — the year filter must still apply.
    db_session.add(
        Factor(
            emission_type_id=EmissionType.food__vegetarian.value,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            classification={},
            values={"ef_kg_co2eq_per_unit": 9.0},
            year=2024,
        )
    )
    await db_session.flush()

    found = await repo.list_by_emission_types(wanted, year=2025)

    assert {f.emission_type_id for f in found} == {e.value for e in wanted}
    assert len(found) == 2


@pytest.mark.asyncio
async def test_list_by_emission_types_empty_input_queries_nothing(db_session):
    """An empty subtree must not degenerate into an unfiltered table scan."""
    repo = FactorRepository(db_session)
    db_session.add(
        Factor(
            emission_type_id=EmissionType.food__vegetarian.value,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            classification={},
            values={"ef_kg_co2eq_per_unit": 1.0},
            year=2025,
        )
    )
    await db_session.flush()

    assert await repo.list_by_emission_types([], year=2025) == []


# ======================================================================
# #2258 — every factor write invalidates the taxonomy cache, but only
# once the write actually commits (never at flush time — a concurrent
# reader between flush and commit would otherwise repopulate the cache
# with the pre-write data it still sees under READ COMMITTED). These
# use the real ``db_session`` fixture, not the mock ``repo`` fixture:
# the deferral hooks real SQLAlchemy session events, which a MagicMock
# session can't participate in.
# ======================================================================


async def _create_factor(repo, db_session) -> Factor:
    factor = Factor(
        emission_type_id=EmissionType.food,
        data_entry_type_id=DataEntryTypeEnum.member,
        classification={},
        values={},
    )
    db_session.add(factor)
    await db_session.flush()
    return factor


@pytest.mark.asyncio
async def test_create_defers_taxonomy_cache_clear_until_commit(db_session):
    repo = FactorRepository(db_session)
    taxonomy_cache.set(("stale-key",), "stale-tree")

    await repo.create(
        Factor(
            emission_type_id=EmissionType.food,
            data_entry_type_id=DataEntryTypeEnum.member,
            classification={},
            values={},
        )
    )
    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"

    await db_session.commit()
    assert taxonomy_cache.get(("stale-key",)) is None


@pytest.mark.asyncio
async def test_create_broadcasts_cache_clear_to_other_pods_after_commit(
    db_session, monkeypatch
):
    """Pins the wiring (#2258 follow-up): a write must eventually call the
    cross-pod broadcast, not just the local ``clear()`` — a refactor that
    drops this call would otherwise leave every other test above green
    while silently regressing cross-pod staleness back to ~120s.
    """
    post_clear = AsyncMock()
    monkeypatch.setattr(taxonomy_cache_broadcast_mod, "_post_clear_to", post_clear)
    repo = FactorRepository(db_session)

    await repo.create(
        Factor(
            emission_type_id=EmissionType.food,
            data_entry_type_id=DataEntryTypeEnum.member,
            classification={},
            values={},
        )
    )
    post_clear.assert_not_awaited()

    await db_session.commit()
    await asyncio.sleep(0)  # let the fire_and_forget task run

    post_clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_defers_taxonomy_cache_clear_until_commit(db_session):
    repo = FactorRepository(db_session)
    factor = await _create_factor(repo, db_session)
    await db_session.commit()
    taxonomy_cache.set(("stale-key",), "stale-tree")

    await repo.update(factor.id, {"values": {"co2": 1}})
    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"

    await db_session.commit()
    assert taxonomy_cache.get(("stale-key",)) is None


@pytest.mark.asyncio
async def test_update_not_found_leaves_cache_untouched(repo):
    """No row was actually changed, so nothing needs invalidating."""
    taxonomy_cache.set(("fresh-key",), "fresh-tree")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    await repo.update(999, {"name": "new"})

    assert taxonomy_cache.get(("fresh-key",)) == "fresh-tree"


@pytest.mark.asyncio
async def test_delete_defers_taxonomy_cache_clear_until_commit(db_session):
    repo = FactorRepository(db_session)
    factor = await _create_factor(repo, db_session)
    await db_session.commit()
    taxonomy_cache.set(("stale-key",), "stale-tree")

    await repo.delete(factor.id)
    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"

    await db_session.commit()
    assert taxonomy_cache.get(("stale-key",)) is None


@pytest.mark.asyncio
async def test_bulk_delete_defers_taxonomy_cache_clear_until_commit(db_session):
    repo = FactorRepository(db_session)
    factor = await _create_factor(repo, db_session)
    await db_session.commit()
    taxonomy_cache.set(("stale-key",), "stale-tree")

    await repo.bulk_delete([factor.id])
    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"

    await db_session.commit()
    assert taxonomy_cache.get(("stale-key",)) is None


@pytest.mark.asyncio
async def test_delete_stale_for_year_defers_taxonomy_cache_clear_until_commit(
    db_session,
):
    """Exercises the real ingestion sweep path (#2258): a factor CSV upload
    that supersedes rows for a (det, year) must not leave the previous
    upload's cached taxonomy tree being served afterwards — but only
    once the sweep is actually durable.
    """
    repo = FactorRepository(db_session)
    db_session.add(
        Factor(
            emission_type_id=EmissionType.food.value,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            classification={},
            values={},
            year=2025,
            last_seen_job_id=1,
        )
    )
    await db_session.flush()
    taxonomy_cache.set(("stale-key",), "stale-tree")

    await repo.delete_stale_for_year(
        2025, det_ids=[DataEntryTypeEnum.member.value], threshold_job_id=2
    )
    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"

    await db_session.commit()
    assert taxonomy_cache.get(("stale-key",)) is None


@pytest.mark.asyncio
async def test_rollback_never_invalidates_taxonomy_cache(db_session):
    """A rolled-back write must never clear the cache — nothing changed."""
    repo = FactorRepository(db_session)
    taxonomy_cache.set(("stale-key",), "stale-tree")

    await repo.create(
        Factor(
            emission_type_id=EmissionType.food,
            data_entry_type_id=DataEntryTypeEnum.member,
            classification={},
            values={},
        )
    )
    await db_session.rollback()

    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"


@pytest.mark.asyncio
async def test_multiple_writes_in_one_transaction_broadcast_once(
    db_session, monkeypatch
):
    """#2258 follow-up: several writes on the same session/transaction
    (e.g. a factor-recompute job looping per-row, all under one commit)
    must collapse into a single post-commit clear + broadcast, not one
    per write — otherwise a large recompute turns one logical
    invalidation into hundreds of redundant cross-pod broadcasts.
    """
    post_clear = AsyncMock()
    monkeypatch.setattr(taxonomy_cache_broadcast_mod, "_post_clear_to", post_clear)
    repo = FactorRepository(db_session)

    for _ in range(3):
        await repo.create(
            Factor(
                emission_type_id=EmissionType.food,
                data_entry_type_id=DataEntryTypeEnum.member,
                classification={},
                values={},
            )
        )

    await db_session.commit()
    await asyncio.sleep(0)

    post_clear.assert_awaited_once()
