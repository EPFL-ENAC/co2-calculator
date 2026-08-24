# codeql[py/unused-global-variable]
"""research facilities inputs deactivated by default

Revision ID: 9c41ab7d3e02
Revises: 277bf6757926
Create Date: 2026-08-24 10:30:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "9c41ab7d3e02"  # noqa: F841
down_revision: str | Sequence[str] | None = "277bf6757926"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841

# Research Facilities module (6) → research_facilities (70), animal_facilities (71).
MODULE_KEY = "6"
SUBMODULE_KEYS = ("70", "71")
FLAGS = ("inputs_deactivated", "csv_deactivated")


def _rows(bind: sa.engine.Connection) -> list[tuple[int, str, dict]]:
    """Every year_configuration row, across all providers (the PK is a pair).

    ``.columns()`` binds the JSON type so the driver deserializes ``config``: a
    bare ``text()`` carries no type information and can hand back a string. A
    non-dict raises rather than defaulting to ``{}`` — writing that back would
    erase every other module's configuration and report success.
    """
    result = bind.execute(
        sa.text(
            "SELECT year, provider::text AS provider, config FROM year_configuration"
        ).columns(year=sa.Integer(), provider=sa.String(), config=sa.JSON())
    )
    rows: list[tuple[int, str, dict]] = []
    for row in result:
        if not isinstance(row.config, dict):
            raise RuntimeError(
                f"year_configuration({row.year}, {row.provider}).config is"
                f" {type(row.config).__name__}, expected dict"
            )
        rows.append((row.year, row.provider, row.config))
    return rows


def _save(bind: sa.engine.Connection, year: int, provider: str, config: dict) -> None:
    # ``provider::text`` on both sides: comparing the enum's own label avoids
    # casting a Python string back into user_provider_enum.
    bind.execute(
        sa.text(
            "UPDATE year_configuration SET config = CAST(:config AS json)"
            " WHERE year = :year AND provider::text = :provider"
        ),
        {"config": json.dumps(config), "year": year, "provider": provider},
    )


def upgrade() -> None:
    """#2007: Research Facilities manual input ships off for existing years.

    ``generate_default_year_config`` only covers years created from now on, and
    the DB survives deploys — without this, every configured year would resolve
    the new form to "active" on the first deploy, the inverse of the ask.

    Written row by row rather than with ``jsonb_set``: ``config`` is ``json``,
    not ``jsonb``, and ``jsonb_set`` silently no-ops when a parent path is
    absent, which would report success while changing nothing.
    """
    bind = op.get_bind()
    for year, provider, config in _rows(bind):
        modules = config.setdefault("modules", {})
        module = modules.setdefault(MODULE_KEY, {})
        submodules = module.setdefault("submodules", {})
        for submodule_key in SUBMODULE_KEYS:
            submodule = submodules.setdefault(submodule_key, {})
            for flag in FLAGS:
                submodule[flag] = True
        _save(bind, year, provider, config)


def downgrade() -> None:
    """Drop the flags; absent resolves to False, the schema default."""
    bind = op.get_bind()
    for year, provider, config in _rows(bind):
        submodules = config.get("modules", {}).get(MODULE_KEY, {}).get("submodules", {})
        for submodule_key in SUBMODULE_KEYS:
            submodule = submodules.get(submodule_key, {})
            for flag in FLAGS:
                submodule.pop(flag, None)
        _save(bind, year, provider, config)
