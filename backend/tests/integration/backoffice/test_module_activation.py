"""Integration tests for module/sub-module activation behavior (issue #1403,
checklist item "Common module behavior").

Covers, at the ``YearConfiguration`` API layer (backend source of truth for
the backoffice Configurator):

- Deactivating one module must not alter unrelated modules' upload state.
- Re-activating a module preserves previously uploaded data (no data loss
  on toggle) — uploads live in ``DataIngestionJob`` rows, keyed
  independently of the module's ``enabled`` flag, so toggling ``enabled``
  must never touch them.
- Sub-module activation/deactivation persists in ``YearConfiguration.config``.

Issue #1433 (sibling PR) reports that deactivating Headcount in the
Configurator visually hides Equipment/Process Emissions/Purchases data.
Its own investigation plan (``1433-headcount-deactivation-deletes-other-
modules-data.md``) ruled out ``_deep_merge`` / the year-configuration
response as the mechanism via code review, but left it unconfirmed pending
a regression test. ``test_deactivating_headcount_does_not_alter_sibling_
modules`` below IS that regression test, scoped to this test suite's layer
(the year-configuration response the Configurator screen renders from). If
this test ever starts failing, the cascade lives in the layer #1403(b)
covers and should be fixed here (not xfail'd) — the plan's suspected
culprits (report-stats/stat-bucket computation, or a frontend gate) are
outside this file's scope and remain #1433's to chase down.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.main import app
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.services.year_config_service import generate_default_year_config

URL = "/api/v1/year-configuration/2025"
YEAR = 2025


def _finished_job(
    *, module_type_id: int, data_entry_type_id: int, target_type: TargetType
) -> DataIngestionJob:
    """A FINISHED+SUCCESS upload job — what a "data already uploaded"
    submodule looks like in the ``latest_*_job`` enrichment.
    """
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
        year=YEAR,
        target_type=target_type,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )


@pytest_asyncio.fixture
async def db_with_multi_module_uploads():
    """Seed one YearConfiguration + DATA_ENTRIES jobs for Headcount
    (member), Equipment (scientific), Purchase (scientific_equipment) and
    Process Emissions — one representative submodule per module — so the
    year-configuration response has real "data uploaded" state to compare
    across a Headcount enable/disable toggle.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        session.add(
            YearConfiguration(
                year=YEAR,
                provider=UserProvider.DEFAULT,
                is_started=False,
                configuration_completed=datetime.now(UTC),
                config=generate_default_year_config(),
            )
        )
        session.add_all(
            [
                _finished_job(
                    module_type_id=int(ModuleTypeEnum.headcount),
                    data_entry_type_id=1,  # member
                    target_type=TargetType.DATA_ENTRIES,
                ),
                _finished_job(
                    module_type_id=int(ModuleTypeEnum.equipment),
                    data_entry_type_id=10,  # scientific
                    target_type=TargetType.DATA_ENTRIES,
                ),
                _finished_job(
                    module_type_id=int(ModuleTypeEnum.purchase),
                    data_entry_type_id=60,  # scientific_equipment
                    target_type=TargetType.DATA_ENTRIES,
                ),
                _finished_job(
                    module_type_id=int(ModuleTypeEnum.process_emissions),
                    data_entry_type_id=50,  # process_emissions
                    target_type=TargetType.DATA_ENTRIES,
                ),
            ]
        )
        await session.commit()
        yield session, async_session

    await engine.dispose()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _admin_user() -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.email = "backoffice-admin@example.com"
    u.institutional_id = "99999"
    u.provider = UserProvider.DEFAULT
    return u


def _wire(monkeypatch, db_factory) -> None:
    app.dependency_overrides[deps_module.get_current_user] = _admin_user

    async def override_get_db():
        async with db_factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db

    async def fake_is_permitted(user, path, action="view"):
        return path == "backoffice.configuration" and action in ("view", "edit")

    monkeypatch.setattr("app.api.v1.year_configuration.is_permitted", fake_is_permitted)

    # ``audit_document_one_current_idx`` is declared with
    # ``postgresql_where=...`` only — a Postgres-only partial-unique index.
    # SQLite's generic ``Index()`` DDL ignores the dialect-specific WHERE
    # clause and creates a fully unique index on (entity_id, entity_type)
    # instead, so a second PATCH to the same year (needed to exercise
    # disable-then-re-enable) trips a UNIQUE constraint that production
    # Postgres never would. Audit trail persistence isn't what these tests
    # cover — stub it out rather than fight the sqlite/pg DDL divergence.
    async def fake_create_audit_entry(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.year_configuration.create_audit_entry", fake_create_audit_entry
    )


def _module_snapshot(config: dict, module_type_id: int) -> dict:
    """Extract the comparable, job-derived fields for one module (drop
    ``enabled``/``incomplete`` — those are expected to change; the point is
    the *upload* fields must not).
    """
    module = config["modules"][str(module_type_id)]
    return {
        sub_key: {
            "latest_data_job": sub_val.get("latest_data_job"),
            "latest_factor_job": sub_val.get("latest_factor_job"),
            "latest_reference_job": sub_val.get("latest_reference_job"),
        }
        for sub_key, sub_val in module["submodules"].items()
    }


def test_deactivating_headcount_does_not_alter_sibling_modules(
    client, monkeypatch, db_with_multi_module_uploads
):
    """#1433 regression pin: disabling Headcount must leave Equipment,
    Purchase and Process Emissions' uploaded-data state byte-for-byte
    unchanged in the year-configuration response — the same response the
    Configurator screen renders module cards from.
    """
    _, factory = db_with_multi_module_uploads
    _wire(monkeypatch, factory)

    before = client.get(URL).json()["config"]
    before_snapshots = {
        m: _module_snapshot(before, m)
        for m in (
            int(ModuleTypeEnum.equipment),
            int(ModuleTypeEnum.purchase),
            int(ModuleTypeEnum.process_emissions),
        )
    }

    patch = client.patch(URL, json={"config": {"modules": {"1": {"enabled": False}}}})
    assert patch.status_code == 200, patch.text
    assert patch.json()["config"]["modules"]["1"]["enabled"] is False

    after = client.get(URL).json()["config"]
    for module_type_id, snapshot in before_snapshots.items():
        assert _module_snapshot(after, module_type_id) == snapshot, (
            f"module {module_type_id}'s upload state changed after "
            "disabling Headcount — #1433 cascade reproduced at the "
            "year-configuration layer"
        )


def test_reactivating_module_preserves_previously_uploaded_data(
    client, monkeypatch, db_with_multi_module_uploads
):
    """Disable then re-enable Headcount: its own member submodule's
    ``latest_data_job`` must still be there — the toggle only flips a bool
    in ``config``, it never touches the ``DataIngestionJob`` rows.
    """
    _, factory = db_with_multi_module_uploads
    _wire(monkeypatch, factory)

    before = client.get(URL).json()["config"]
    headcount_before = _module_snapshot(before, int(ModuleTypeEnum.headcount))
    assert headcount_before["1"]["latest_data_job"] is not None  # sanity

    client.patch(URL, json={"config": {"modules": {"1": {"enabled": False}}}})
    reenabled = client.patch(
        URL, json={"config": {"modules": {"1": {"enabled": True}}}}
    )
    assert reenabled.status_code == 200, reenabled.text
    assert reenabled.json()["config"]["modules"]["1"]["enabled"] is True

    after = client.get(URL).json()["config"]
    assert _module_snapshot(after, int(ModuleTypeEnum.headcount)) == headcount_before


def test_submodule_activation_persists_in_config(
    client, monkeypatch, db_with_multi_module_uploads
):
    """Toggling a sub-module's ``enabled`` flag persists in
    ``YearConfiguration.config`` and survives a re-fetch.
    """
    _, factory = db_with_multi_module_uploads
    _wire(monkeypatch, factory)

    patch = client.patch(
        URL,
        json={"config": {"modules": {"4": {"submodules": {"10": {"enabled": False}}}}}},
    )
    assert patch.status_code == 200, patch.text
    assert (
        patch.json()["config"]["modules"]["4"]["submodules"]["10"]["enabled"] is False
    )

    refetched = client.get(URL).json()["config"]
    assert refetched["modules"]["4"]["submodules"]["10"]["enabled"] is False
    # Sibling submodule untouched by the sub-module-scoped patch.
    assert refetched["modules"]["4"]["submodules"]["11"]["enabled"] is True
