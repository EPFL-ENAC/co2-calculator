"""Tests for the "Incomplete" tag computation (issue #1403 checklist item):

    "Incomplete" tag persists at sub-module/module level until required
    files (factors, references where applicable) are uploaded, and clears
    once upload is complete.

The logic lives in ``app.api.v1.year_configuration._annotate_module_incomplete``
(+ ``_submodule_incomplete_reasons``). Per the plan, these are exercised
directly with varied ``YearConfiguration.config`` module fixtures (missing
factor, missing reference, fully complete, disabled) rather than a slow
multi-step upload simulation — the function is pure (mutates the dict it's
given, no I/O), so no DB is needed for that part.

The final test drives the real ``GET /year-configuration/{year}`` endpoint
with every mandatory upload seeded, to pin the "ready to open" *presence*
case (slice (a) of #1403 covers the *absence* case on a fresh year).
"""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.api.v1.year_configuration import _annotate_module_incomplete
from app.core.submodule_mandatoriness import (
    MODULES_REQUIRING_COMMON_FACTOR,
    SUBMODULE_MANDATORINESS,
)
from app.main import app
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.services.year_config_service import generate_default_year_config

# ---------------------------------------------------------------------------
# Pure unit-style tests against ``_annotate_module_incomplete``
# ---------------------------------------------------------------------------

_HEADCOUNT = int(ModuleTypeEnum.headcount)
# DataEntryTypeEnum.member — mandatory_factor=True, mandatory_reference=False
_MEMBER = 1
_EQUIPMENT = int(ModuleTypeEnum.equipment)
# DataEntryTypeEnum.scientific — noFactors, covered by common factor
_SCIENTIFIC = 10
_TRAVEL = int(ModuleTypeEnum.professional_travel)
# DataEntryTypeEnum.train — mandatory_factor=True, mandatory_reference=True
_TRAIN = 21


def test_submodule_missing_factor_flags_incomplete():
    """A module submodule requiring a factor with no ``latest_factor_job``
    is incomplete, and the reason is surfaced."""
    module_val = {
        "enabled": True,
        "submodules": {str(_MEMBER): {"enabled": True, "latest_factor_job": None}},
    }
    _annotate_module_incomplete(module_val, _HEADCOUNT)

    sub = module_val["submodules"][str(_MEMBER)]
    assert sub["incomplete"] is True
    assert sub["incomplete_reasons"] == ["missing_factor"]
    assert module_val["incomplete"] is True


def test_submodule_missing_reference_flags_incomplete():
    """Train requires both factor and reference; factor present, reference
    missing → still incomplete, reason pinpoints the reference."""
    module_val = {
        "enabled": True,
        "submodules": {
            str(_TRAIN): {
                "enabled": True,
                "latest_factor_job": {"job_id": 1},
                "latest_reference_job": None,
            }
        },
    }
    _annotate_module_incomplete(module_val, _TRAVEL)

    sub = module_val["submodules"][str(_TRAIN)]
    assert sub["incomplete"] is True
    assert sub["incomplete_reasons"] == ["missing_reference"]
    assert module_val["incomplete"] is True


def test_fully_complete_submodule_clears_incomplete():
    """Every mandatory upload present → incomplete clears at both levels."""
    module_val = {
        "enabled": True,
        "submodules": {
            str(_TRAIN): {
                "enabled": True,
                "latest_factor_job": {"job_id": 1},
                "latest_reference_job": {"job_id": 2},
            }
        },
    }
    _annotate_module_incomplete(module_val, _TRAVEL)

    sub = module_val["submodules"][str(_TRAIN)]
    assert sub["incomplete"] is False
    assert sub["incomplete_reasons"] == []
    assert module_val["incomplete"] is False


def test_disabled_module_forces_incomplete_false_despite_missing_uploads():
    """A disabled module is never "incomplete" — matches the legacy
    frontend gate (nothing to upload for a module nobody sees)."""
    module_val = {
        "enabled": False,
        "submodules": {str(_MEMBER): {"enabled": True, "latest_factor_job": None}},
    }
    _annotate_module_incomplete(module_val, _HEADCOUNT)

    assert module_val["incomplete"] is False


def test_disabled_submodule_does_not_drive_module_incomplete():
    """An incomplete submodule that is itself disabled must not roll up
    into the module-level flag — only *enabled* submodules count."""
    module_val = {
        "enabled": True,
        "submodules": {
            str(_MEMBER): {"enabled": False, "latest_factor_job": None},
        },
    }
    _annotate_module_incomplete(module_val, _HEADCOUNT)

    # The submodule itself still reports incomplete (it IS missing its
    # factor) — only the module-level rollup ignores it.
    assert module_val["submodules"][str(_MEMBER)]["incomplete"] is True
    assert module_val["incomplete"] is False


def test_common_factor_module_needs_module_level_factor_job():
    """Equipment is in ``MODULES_REQUIRING_COMMON_FACTOR``: even with every
    submodule individually satisfied (they're all noFactors), the module
    stays incomplete until the module-level common factor upload lands."""
    assert _EQUIPMENT in MODULES_REQUIRING_COMMON_FACTOR
    module_val = {
        "enabled": True,
        "latest_common_factor_job": None,
        "submodules": {
            str(_SCIENTIFIC): {"enabled": True, "latest_factor_job": None},
        },
    }
    _annotate_module_incomplete(module_val, _EQUIPMENT)

    # The submodule itself has no mandatory factor (noFactors) — not
    # individually incomplete.
    assert module_val["submodules"][str(_SCIENTIFIC)]["incomplete"] is False
    # But the module rolls up incomplete via the missing common factor.
    assert module_val["incomplete"] is True


def test_common_factor_present_clears_module_incomplete():
    """Same shape as above, but the common factor job is now present —
    the module clears."""
    module_val = {
        "enabled": True,
        "latest_common_factor_job": {"job_id": 9},
        "submodules": {
            str(_SCIENTIFIC): {"enabled": True, "latest_factor_job": None},
        },
    }
    _annotate_module_incomplete(module_val, _EQUIPMENT)

    assert module_val["incomplete"] is False


def test_common_factor_satisfies_submodule_missing_own_factor():
    """A submodule with ``mandatory_factor=True`` is satisfied by the
    module's common-factor job even without its own — matches the legacy
    frontend fallback rule (``_submodule_incomplete_reasons`` docstring)."""
    # additional_purchases (67) is the one purchase submodule with its own
    # mandatory_factor=True; the module (purchase=5) is also in
    # MODULES_REQUIRING_COMMON_FACTOR.
    purchase = int(ModuleTypeEnum.purchase)
    assert SUBMODULE_MANDATORINESS[(purchase, 67)].mandatory_factor is True
    assert purchase in MODULES_REQUIRING_COMMON_FACTOR

    module_val = {
        "enabled": True,
        "latest_common_factor_job": {"job_id": 9},
        "submodules": {"67": {"enabled": True, "latest_factor_job": None}},
    }
    _annotate_module_incomplete(module_val, purchase)

    assert module_val["submodules"]["67"]["incomplete"] is False
    assert module_val["incomplete"] is False


# ---------------------------------------------------------------------------
# Endpoint-level "ready to open" — presence case (every module complete)
# ---------------------------------------------------------------------------

YEAR = 2025
URL = f"/api/v1/year-configuration/{YEAR}"


def _seed_jobs_for_full_completion() -> list[DataIngestionJob]:
    """One finished factor/reference job per mandatory (module, det) pair,
    plus a module-level common-factor job for every module in
    ``MODULES_REQUIRING_COMMON_FACTOR`` — enough to satisfy every
    ``incomplete`` rule across the whole default config."""
    jobs: list[DataIngestionJob] = []

    def _job(module_type_id, data_entry_type_id, target_type) -> DataIngestionJob:
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

    for module_type, dets in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items():
        for det in dets:
            rules = SUBMODULE_MANDATORINESS.get((int(module_type), int(det)))
            if rules is None:
                continue
            if rules.mandatory_factor:
                jobs.append(_job(int(module_type), int(det), TargetType.FACTORS))
            if rules.mandatory_reference:
                jobs.append(_job(int(module_type), int(det), TargetType.REFERENCE_DATA))

    for module_type_id in MODULES_REQUIRING_COMMON_FACTOR:
        jobs.append(_job(module_type_id, None, TargetType.FACTORS))

    return jobs


@pytest_asyncio.fixture
async def db_fully_uploaded_year():
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
                configuration_completed=datetime.now(timezone.utc),
                config=generate_default_year_config(),
            )
        )
        session.add_all(_seed_jobs_for_full_completion())
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


def test_every_module_reports_complete_once_all_mandatory_uploads_present(
    client, monkeypatch, db_fully_uploaded_year
):
    """Presence case: once every mandatory factor/reference (submodule and
    common) is uploaded, the year-configuration response marks every
    module — and every submodule — ``incomplete=False``. This is the
    signal the Configurator reads to enable "Ouvrir l'année pour les
    utilisateurs" (the absence case is covered in slice (a))."""
    _, factory = db_fully_uploaded_year
    app.dependency_overrides[deps_module.get_current_user] = lambda: type(
        "U", (), {"id": 1, "provider": UserProvider.DEFAULT, "institutional_id": "1"}
    )()

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db

    response = client.get(URL)
    assert response.status_code == 200, response.text
    modules = response.json()["config"]["modules"]

    incomplete_modules = {
        m: val["incomplete"] for m, val in modules.items() if val["incomplete"]
    }
    assert incomplete_modules == {}, (
        f"expected every module complete, still incomplete: {incomplete_modules}"
    )
    for module_key, module_val in modules.items():
        for sub_key, sub_val in module_val["submodules"].items():
            assert sub_val["incomplete"] is False, (
                f"module {module_key} submodule {sub_key} still incomplete: "
                f"{sub_val['incomplete_reasons']}"
            )
