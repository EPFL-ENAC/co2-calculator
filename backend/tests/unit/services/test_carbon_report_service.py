import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.constants import ModuleStatus
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReportModule, CarbonReportType
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import ALL_MODULE_TYPE_IDS, ModuleTypeEnum
from app.schemas.carbon_report import CarbonReportCreate, CarbonReportUpdate
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)  # Ensure a clean slate
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_service_create_and_get(async_session):
    service = CarbonReportService(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await service.create(data)
    assert inv.id is not None
    fetched = await service.get(inv.id)
    assert fetched is not None
    assert fetched.unit_id == 1
    assert fetched.year == 2025


@pytest.mark.asyncio
async def test_service_create_auto_creates_modules(async_session):
    """Test that creating an carbon_report auto-creates all module records."""
    service = CarbonReportService(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await service.create(data)

    # Check that modules were auto-created
    modules = await service.module_service.list_modules(inv.id)
    assert len(modules) == len(ALL_MODULE_TYPE_IDS)

    # All should have NOT_STARTED status
    for mod in modules:
        assert mod.status == ModuleStatus.NOT_STARTED
        assert mod.carbon_report_id == inv.id


@pytest.mark.asyncio
async def test_service_list_inventories_by_unit(async_session):
    service = CarbonReportService(async_session)
    await service.create(CarbonReportCreate(year=2025, unit_id=1))
    await service.create(CarbonReportCreate(year=2026, unit_id=1))
    await service.create(CarbonReportCreate(year=2025, unit_id=2))
    items = await service.list_by_unit(1)
    assert len(items) == 2


@pytest.mark.asyncio
async def test_service_update_and_delete(async_session):
    service = CarbonReportService(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await service.create(data)

    update = CarbonReportUpdate(year=2026, unit_id=1)
    updated = await service.update(inv.id, update)
    assert updated.year == 2026

    # Delete should also delete associated modules
    deleted = await service.delete(inv.id)
    assert deleted is True
    assert await service.get(inv.id) is None

    # Modules should also be deleted
    modules = await service.module_service.list_modules(inv.id)
    assert len(modules) == 0


@pytest.mark.asyncio
async def test_module_status_update(async_session):
    """Test updating module status via service."""
    service = CarbonReportService(async_session)
    inv = await service.create(CarbonReportCreate(year=2025, unit_id=1))

    # Update a module status
    module_type_id = 1  # my-lab
    updated = await service.module_service.update_status(
        inv.id, module_type_id, ModuleStatus.IN_PROGRESS
    )
    assert updated is not None
    assert updated.status == ModuleStatus.IN_PROGRESS

    # Verify it persists
    modules = await service.module_service.list_modules(inv.id)
    headcount_mod = next(m for m in modules if m.module_type_id == module_type_id)
    assert headcount_mod.status == ModuleStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_recompute_report_stats_merges_by_additional_value(async_session):
    service = CarbonReportService(async_session)
    report = await service.create(CarbonReportCreate(year=2025, unit_id=1))

    modules = await service.module_service.list_modules(report.id)
    by_type = {m.module_type_id: m for m in modules}
    headcount = by_type[int(ModuleTypeEnum.headcount)]
    travel = by_type[int(ModuleTypeEnum.professional_travel)]

    db_headcount = await async_session.get(CarbonReportModule, headcount.id)
    db_travel = await async_session.get(CarbonReportModule, travel.id)
    assert db_headcount is not None
    assert db_travel is not None

    db_headcount.stats = {
        "buckets": {
            "food": {
                "scope": 3,
                "additional": True,
                "total_kg": 1.0,
                "by_emission_type": {"10001": 1.0},
                "by_additional_value": {"10001": 2.0},
            }
        },
        "total": 1.0,
        "by_emission_type": {"10001": 1.0},
        "by_additional_value": {"10001": 2.0},
        "computed_at": "2026-01-01T00:00:00+00:00",
        "entry_count": 1,
    }
    db_travel.stats = {
        "buckets": {
            "professional_travel": {
                "scope": 3,
                "additional": False,
                "total_kg": 3.0,
                "by_emission_type": {"50101": 3.0},
                "by_additional_value": {"50101": 4.0},
            }
        },
        "total": 3.0,
        "by_emission_type": {"50101": 3.0},
        "by_additional_value": {"50101": 4.0},
        "computed_at": "2026-01-01T00:00:00+00:00",
        "entry_count": 1,
    }
    await async_session.flush()

    await service.recompute_report_stats(report.id)

    fetched = await service.get(report.id)
    assert fetched is not None
    assert fetched.stats is not None
    assert fetched.stats["by_additional_value"]["10001"] == pytest.approx(2.0)
    assert fetched.stats["by_additional_value"]["50101"] == pytest.approx(4.0)
    assert fetched.stats["buckets"]["professional_travel"]["total_kg"] == 3.0
    assert fetched.stats["total"] == pytest.approx(4.0)


# ── Simulator Explore: get_explore / create_explore ───────────────────────────


@pytest.mark.asyncio
async def test_get_explore_returns_none_when_not_found(async_session):
    """get_explore is idempotent: returns None without creating anything."""
    service = CarbonReportService(async_session)
    result = await service.get_explore(unit_id=1, reference_year=2024, created_by=10)
    assert result is None


@pytest.mark.asyncio
async def test_get_explore_is_idempotent_on_empty_db(async_session):
    """Calling get_explore twice on an empty DB still returns None both times."""
    service = CarbonReportService(async_session)
    first = await service.get_explore(unit_id=1, reference_year=2024, created_by=10)
    second = await service.get_explore(unit_id=1, reference_year=2024, created_by=10)
    assert first is None
    assert second is None


@pytest.mark.asyncio
async def test_create_explore_creates_report_and_modules(async_session):
    """create_explore creates a SIMULATOR_EXPLORE report with all modules."""
    service = CarbonReportService(async_session)
    result = await service.create_explore(unit_id=1, reference_year=2024, created_by=10)

    assert result.id is not None
    assert result.year == 2024
    assert result.unit_id == 1

    modules = await service.module_service.list_modules(result.id)
    assert len(modules) == len(ALL_MODULE_TYPE_IDS)
    for mod in modules:
        assert mod.status == ModuleStatus.NOT_STARTED


@pytest.mark.asyncio
async def test_get_explore_returns_existing_report(async_session):
    """get_explore finds the report created by create_explore."""
    service = CarbonReportService(async_session)
    created = await service.create_explore(
        unit_id=1, reference_year=2024, created_by=10
    )
    fetched = await service.get_explore(unit_id=1, reference_year=2024, created_by=10)

    assert fetched is not None
    assert fetched.id == created.id


@pytest.mark.asyncio
async def test_get_explore_does_not_cross_units(async_session):
    """get_explore for another unit returns None even if that unit has a report."""
    service = CarbonReportService(async_session)
    await service.create_explore(unit_id=1, reference_year=2024, created_by=10)
    result = await service.get_explore(unit_id=2, reference_year=2024, created_by=10)
    assert result is None


@pytest.mark.asyncio
async def test_get_explore_does_not_cross_users(async_session):
    """Explore sandboxes are private per user within the same unit (#2293)."""
    service = CarbonReportService(async_session)
    first = await service.create_explore(unit_id=1, reference_year=2024, created_by=10)

    other = await service.get_explore(unit_id=1, reference_year=2024, created_by=11)
    assert other is None

    second = await service.create_explore(unit_id=1, reference_year=2024, created_by=11)
    assert second.id != first.id

    fetched_first = await service.get_explore(
        unit_id=1, reference_year=2024, created_by=10
    )
    fetched_second = await service.get_explore(
        unit_id=1, reference_year=2024, created_by=11
    )
    assert fetched_first is not None and fetched_first.id == first.id
    assert fetched_second is not None and fetched_second.id == second.id


@pytest.mark.asyncio
async def test_get_explore_does_not_cross_years(async_session):
    """get_explore for a different year returns None."""
    service = CarbonReportService(async_session)
    await service.create_explore(unit_id=1, reference_year=2024, created_by=10)
    result = await service.get_explore(unit_id=1, reference_year=2023, created_by=10)
    assert result is None


# ── bulk_upsert: project-ID resolution ────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_upsert_resolves_project_ids_before_repo_call(async_session):
    """Service enriches every item with a non-null carbon_project_id.

    Two items for unit_id=1 share the same project; unit_id=2 gets its own.
    The actual ON CONFLICT SQL runs only in PostgreSQL integration tests;
    here we confirm the service-layer enrichment is correct.
    """
    service = CarbonReportService(async_session)

    received: list[CarbonReportCreate] = []

    async def fake_bulk_upsert(data: list) -> list:
        received.extend(data)
        return []

    service.repo.bulk_upsert = fake_bulk_upsert

    items = [
        CarbonReportCreate(year=2024, unit_id=1),
        CarbonReportCreate(year=2025, unit_id=1),
        CarbonReportCreate(year=2024, unit_id=2),
    ]
    await service.bulk_upsert(items)

    assert len(received) == 3
    assert all(d.carbon_project_id is not None for d in received)

    unit1_ids = [d.carbon_project_id for d in received if d.unit_id == 1]
    unit2_ids = [d.carbon_project_id for d in received if d.unit_id == 2]

    # Both unit_id=1 rows share one project
    assert unit1_ids[0] == unit1_ids[1]
    # unit_id=2 has a distinct project
    assert unit1_ids[0] != unit2_ids[0]


@pytest.mark.asyncio
async def test_recompute_report_stats_excludes_inactive_modules(async_session):
    """Simulator Plan 'Active' checkbox off ⇒ module out of sums and progress."""
    service = CarbonReportService(async_session)
    report = await service.create(CarbonReportCreate(year=2025, unit_id=1))

    modules = await service.module_service.list_modules(report.id)
    by_type = {m.module_type_id: m for m in modules}
    headcount = by_type[int(ModuleTypeEnum.headcount)]
    travel = by_type[int(ModuleTypeEnum.professional_travel)]

    db_headcount = await async_session.get(CarbonReportModule, headcount.id)
    db_travel = await async_session.get(CarbonReportModule, travel.id)
    assert db_headcount is not None
    assert db_travel is not None

    stats = {
        "buckets": {
            "professional_travel": {
                "scope": 3,
                "additional": False,
                "total_kg": 3.0,
                "by_emission_type": {"50101": 3.0},
                "by_additional_value": {"50101": 4.0},
            }
        },
        "total": 3.0,
        "by_emission_type": {"50101": 3.0},
        "by_additional_value": {"50101": 4.0},
        "computed_at": "2026-01-01T00:00:00+00:00",
        "entry_count": 1,
    }
    db_headcount.stats = {
        "buckets": {
            "food": {
                "scope": 3,
                "additional": True,
                "total_kg": 1.0,
                "by_emission_type": {"10001": 1.0},
                "by_additional_value": {"10001": 2.0},
            }
        },
        "total": 1.0,
        "by_emission_type": {"10001": 1.0},
        "by_additional_value": {"10001": 2.0},
        "computed_at": "2026-01-01T00:00:00+00:00",
        "entry_count": 1,
    }
    db_travel.stats = stats
    db_travel.is_active = False
    await async_session.flush()

    await service.recompute_report_stats(report.id)

    fetched = await service.get(report.id)
    assert fetched is not None
    assert fetched.stats is not None
    assert fetched.stats["total"] == pytest.approx(1.0)
    assert "professional_travel" not in fetched.stats["buckets"]

    toggled = await service.module_service.update_is_active(
        report.id, int(ModuleTypeEnum.professional_travel), True
    )
    assert toggled is not None and toggled.is_active is True
    await service.recompute_report_stats(report.id)
    fetched = await service.get(report.id)
    assert fetched is not None and fetched.stats is not None
    assert fetched.stats["total"] == pytest.approx(4.0)


async def test_recompute_report_stats_marks_plan_modules_validated(async_session):
    """Simulator Plan has no validate step, so its buckets count as validated.

    Without this the planner results chart zeroes every bar: it renders a
    module row only when its category is in ``validated_categories``, which
    derives from ``validated_buckets``.
    """
    project = CarbonProject(
        unit_id=1,
        carbon_report_type=CarbonReportType.SIMULATOR_PLAN,
        name="proj",
    )
    async_session.add(project)
    await async_session.flush()

    service = CarbonReportService(async_session)
    report = await service.create(
        CarbonReportCreate(year=2027, unit_id=1, carbon_project_id=project.id)
    )

    modules = await service.module_service.list_modules(report.id)
    travel = next(
        m
        for m in modules
        if m.module_type_id == int(ModuleTypeEnum.professional_travel)
    )
    db_travel = await async_session.get(CarbonReportModule, travel.id)
    assert db_travel is not None
    assert db_travel.status != ModuleStatus.VALIDATED
    db_travel.stats = {
        "buckets": {
            "professional_travel": {
                "scope": 3,
                "additional": False,
                "total_kg": 3.0,
                "by_emission_type": {"50101": 3.0},
                "by_additional_value": {},
            }
        },
        "total": 3.0,
        "by_emission_type": {"50101": 3.0},
        "by_additional_value": {},
        "computed_at": "2026-01-01T00:00:00+00:00",
        "entry_count": 1,
    }
    await async_session.flush()

    await service.recompute_report_stats(report.id)

    fetched = await service.get(report.id)
    assert fetched is not None and fetched.stats is not None
    assert "professional_travel" in fetched.stats["validated_buckets"]
    assert fetched.stats["validated_total"] == pytest.approx(3.0)


# ======================================================================
# #2050 J4 — one grouped query for entry count and headcount FTE
# ======================================================================


@pytest.mark.asyncio
async def test_entry_counts_and_fte_matches_the_two_queries_it_replaces(
    async_session,
):
    """One grouped query now returns both the entry count and the headcount
    FTE sum. Asserted against hand-computed values including the two edges
    that would otherwise be silently wrong: a non-headcount module (gets a
    count, must get no FTE entry) and an entry with no ``fte`` key (must
    still be counted).
    """
    headcount = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status=ModuleStatus.IN_PROGRESS,
    )
    travel = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status=ModuleStatus.IN_PROGRESS,
    )
    async_session.add_all([headcount, travel])
    await async_session.flush()

    for data in ({"fte": 2.0}, {"fte": 3.5}, {"name": "no fte here"}):
        async_session.add(
            DataEntry(
                carbon_report_module_id=headcount.id,
                data_entry_type_id=DataEntryTypeEnum.member.value,
                data=data,
            )
        )
    async_session.add(
        DataEntry(
            carbon_report_module_id=travel.id,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            data={"distance_km": 100},
        )
    )
    await async_session.flush()

    service = CarbonReportModuleService(async_session)
    counts, fte = await service._entry_counts_and_fte([headcount, travel])

    assert counts[headcount.id] == 3
    assert counts[travel.id] == 1
    assert fte[headcount.id] == pytest.approx(5.5)
    # Non-headcount modules carry no FTE at all, exactly as before.
    assert travel.id not in fte


# ── get-or-create race guards (#2483) ─────────────────────────────────────────


def _duplicate_key_error() -> IntegrityError:
    return IntegrityError("INSERT", {}, Exception("duplicate key"))


def _flaky_first_flush(async_session, monkeypatch):
    """Make the first flush raise like a unique-index loser, then behave.

    The SQLite test schema intentionally omits the partial unique indexes,
    so the loser's UniqueViolation is injected at the flush boundary.
    """
    real_flush = async_session.flush
    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _duplicate_key_error()
        return await real_flush(*args, **kwargs)

    monkeypatch.setattr(async_session, "flush", flaky)


@pytest.mark.asyncio
async def test_create_explore_project_race_returns_winner(async_session, monkeypatch):
    service = CarbonReportService(async_session)
    winner = CarbonProject(
        unit_id=1,
        carbon_report_type=CarbonReportType.SIMULATOR_EXPLORE,
        created_by=7,
    )
    async_session.add(winner)
    await async_session.flush()

    _flaky_first_flush(async_session, monkeypatch)
    recovered = await service._create_explore_project(1, 7)
    assert recovered.id == winner.id


@pytest.mark.asyncio
async def test_create_calculator_project_race_returns_winner(
    async_session, monkeypatch
):
    service = CarbonReportService(async_session)
    winner = CarbonProject(unit_id=1, carbon_report_type=CarbonReportType.CALCULATOR)
    async_session.add(winner)
    await async_session.flush()

    _flaky_first_flush(async_session, monkeypatch)
    recovered = await service._create_project(1, CarbonReportType.CALCULATOR)
    assert recovered.id == winner.id


@pytest.mark.asyncio
async def test_create_explore_report_race_returns_winner(async_session, monkeypatch):
    service = CarbonReportService(async_session)
    winner = await service.create_explore(unit_id=1, reference_year=2025, created_by=7)

    async def losing_insert(_data):
        raise _duplicate_key_error()

    monkeypatch.setattr(service.repo, "create", losing_insert)
    recovered = await service.create_explore(
        unit_id=1, reference_year=2025, created_by=7
    )
    assert recovered.id == winner.id


# ── report-creation statement budget (#2449 Track B) ──────────────────────────


@pytest.mark.asyncio
async def test_report_creation_statement_budget(async_session):
    """Creating a report must stay a handful of statements.

    Regression for #2449 Track B: the per-module ``session.refresh`` loops
    added 9 SELECT round-trips per report (~200 statements on a 10-year
    grow). The cap is generous on purpose — it only has to catch the
    reintroduction of per-object chatter, not exact statement shapes.
    """
    service = CarbonReportService(async_session)
    engine = async_session.bind
    statements: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _count)
    try:
        await service.create(CarbonReportCreate(year=2025, unit_id=1))
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _count)

    assert len(statements) <= 12, statements
