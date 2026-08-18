"""Round-trip test for the ``quantity`` → ``quantity_kg`` data migration (#2025).

Deployed DBs hold process-emissions entries written under the old JSON
key, and the handler formula reads ``quantity_kg`` — a row the migration
misses silently stops computing, which is the "looks complete, is wrong"
failure the guardrails rank worst.  So the rewrite itself needs pinning,
not just "the migration applies" (``tests/integration/test_alembic_migrations.py``
covers that).

The migration's statements are imported from the revision module and run
against this package's throwaway container, rather than driving
``alembic upgrade`` in a subprocess: ``scripts/manage_db`` and
``alembic/env.py`` both resolve the target DB from ``settings.DB_URL``,
and ``Settings.settings_customise_sources`` ranks ``.env`` above real env
vars — so a subprocess-driven migration test runs against whatever
``backend/.env`` points at, not the container.  Importing the SQL keeps
the test on the fixture DSN and still exercises the exact shipped
statements.

Lives in this package because ``pg_dsn`` (function-scoped, schema rebuilt
per test) is defined in its conftest.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.module_type import ModuleTypeEnum

from .conftest import seeded_year_with_units

_REVISION_PATH = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "2026_08_18_1147-09ec5dcb3688_rename_process_emissions_quantity_to_.py"
)

# ``DataEntryTypeEnum.process_emissions`` / ``it_equipment`` — the latter is a
# *purchase* submodule (declared under ``# purchase`` in the enum, handled by
# ``PurchaseModuleHandler``), used here as the control: purchase entries keep
# their own unrelated ``quantity`` field and must survive the migration intact.
_DET_PROCESS_EMISSIONS = 50
_DET_PURCHASE_IT_EQUIPMENT = 61


def _load_revision():
    spec = importlib.util.spec_from_file_location("_rev_09ec5dcb3688", _REVISION_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load revision module at {_REVISION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _seed(engine, *, entry_id: int, det: int, crm_id: int, data: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO data_entries
                    (id, data_entry_type_id, carbon_report_module_id, data,
                     created_at, updated_at)
                VALUES (:id, :det, :crm, CAST(:data AS json), now(), now())
                """
            ),
            {"id": entry_id, "det": det, "crm": crm_id, "data": data},
        )


async def _data(engine, entry_id: int) -> dict:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT data FROM data_entries WHERE id = :id"), {"id": entry_id}
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_quantity_kg_migration_roundtrip(pg_dsn) -> None:
    """Rewrite is correct, scoped to det 50, idempotent, and reversible."""
    revision = _load_revision()
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        # data_entries.carbon_report_module_id is a NOT NULL FK, so the
        # entries need a real unit → report → module tree to hang from.
        async with Sf() as s:
            seeded = await seeded_year_with_units(s, year=2025, n_units=1)
        unit = seeded.units[0]
        crm_id = seeded.modules_by_unit_and_type[
            (unit.id, int(ModuleTypeEnum.process_emissions))
        ].id

        await _seed(
            engine,
            entry_id=9001,
            det=_DET_PROCESS_EMISSIONS,
            crm_id=crm_id,
            data='{"category": "CH4", "quantity": 12.5}',
        )
        await _seed(
            engine,
            entry_id=9002,
            det=_DET_PURCHASE_IT_EQUIPMENT,
            crm_id=crm_id,
            data='{"name": "laptop", "quantity": 3}',
        )

        async with engine.begin() as conn:
            await conn.execute(text(revision.UPGRADE_SQL))

        migrated = await _data(engine, 9001)
        assert migrated["quantity_kg"] == 12.5, migrated
        assert "quantity" not in migrated, f"old key survived: {migrated}"
        assert migrated["category"] == "CH4", f"sibling keys disturbed: {migrated}"

        control = await _data(engine, 9002)
        assert control == {"name": "laptop", "quantity": 3}, (
            f"a non-process-emissions entry was rewritten: {control}"
        )

        # The ``? 'quantity'`` guard makes a re-run a no-op; without it the
        # second pass would overwrite quantity_kg with a JSON null.
        async with engine.begin() as conn:
            await conn.execute(text(revision.UPGRADE_SQL))
        assert await _data(engine, 9001) == migrated, "upgrade is not idempotent"

        async with engine.begin() as conn:
            await conn.execute(text(revision.DOWNGRADE_SQL))
        reverted = await _data(engine, 9001)
        assert reverted == {"category": "CH4", "quantity": 12.5}, (
            f"downgrade is not the exact inverse: {reverted}"
        )
    finally:
        await engine.dispose()
