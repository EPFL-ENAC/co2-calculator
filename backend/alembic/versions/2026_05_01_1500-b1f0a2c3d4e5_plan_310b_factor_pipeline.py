# codeql[py/unused-global-variable]
"""plan 310b factor pipeline schema

Revision ID: b1f0a2c3d4e5
Revises: e528e0d649cd
Create Date: 2026-05-01 15:00:00.000000

Changes:
  1. factors.classification → JSONB so Postgres normalises key order
     alphabetically; (classification::text) becomes deterministic regardless
     of dict insertion order in Python.
  2. Strip the legacy ``"year"`` key from existing classification dicts.
     ``base_factor_csv_provider._process_row`` used to copy ``self.year``
     into ``classification`` before persisting; the dedicated ``year``
     column already carries the same data, and duplicating it inside
     ``classification`` made ``classification::text`` writer-dependent
     (any new path forgetting the inject would silently insert a
     duplicate).  Strip happens BEFORE the unique index in step 3 so the
     index is built against the year-less representation.
  3. Two partial unique indexes on factor identity:
       (data_entry_type_id, year, emission_type_id, classification::text)
         WHERE year IS NOT NULL
       (data_entry_type_id, emission_type_id, classification::text)
         WHERE year IS NULL
     Two indexes because NULL ≠ NULL in a unique index expression.
  4. factors.last_seen_job_id INT FK to data_ingestion_jobs(id) so operators
     can detect factors not present in the latest CSV upload.
  5. ALTER TYPE entity_type_enum ADD VALUE 'GLOBAL_PER_YEAR' for unit-sync jobs.
     Postgres ≥ 12 supports ADD VALUE in any transaction. Cannot be reversed
     (no DROP VALUE), so downgrade leaves the enum value in place.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


revision: str = "b1f0a2c3d4e5"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "e528e0d649cd"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # 1. classification JSON → JSONB
    op.alter_column(
        "factors",
        "classification",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="classification::jsonb",
    )

    # 2. Drop the redundant "year" key from existing classification dicts.
    # MUST run before the unique index in step 3 so the index is built on
    # the canonical year-less representation; otherwise the index would
    # bake the legacy duplicated-year shape into uniqueness comparisons.
    # Idempotent: if the key is already absent, ``-`` is a no-op.
    op.execute(
        "UPDATE factors "
        "SET classification = classification - 'year' "
        "WHERE classification ? 'year'"
    )

    # 3. Partial unique indexes on factor identity
    op.execute(
        "CREATE UNIQUE INDEX uq_factor_identity "
        "ON factors (data_entry_type_id, year, emission_type_id, "
        "(classification::text)) "
        "WHERE year IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_factor_identity_no_year "
        "ON factors (data_entry_type_id, emission_type_id, "
        "(classification::text)) "
        "WHERE year IS NULL"
    )

    # 3. last_seen_job_id column + supporting index
    op.add_column(
        "factors",
        sa.Column("last_seen_job_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_factors_last_seen_job_id",
        "factors",
        "data_ingestion_jobs",
        ["last_seen_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_factors_last_seen_job_id",
        "factors",
        ["last_seen_job_id"],
        unique=False,
    )

    # 4. EntityType.GLOBAL_PER_YEAR for unit-sync jobs.
    # Wrapped in a DO block so re-runs don't error on existing values.
    op.execute(
        "DO $$ BEGIN "
        "ALTER TYPE entity_type_enum ADD VALUE 'GLOBAL_PER_YEAR' "
        "BEFORE 'MODULE_PER_YEAR'; "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$;"
    )


def downgrade() -> None:
    """Downgrade schema.

    Notes:
    - ALTER TYPE ADD VALUE cannot be reversed in Postgres (no DROP VALUE).
      The 'GLOBAL_PER_YEAR' enum value stays after downgrade — harmless if
      no jobs reference it.
    - The "year"-key strip in step 2 is not reversed.  Re-injecting the
      key would require knowing each row's writer-of-origin (CSV vs seed
      script), which we do not track.  All current writers should already
      have stopped emitting the duplicated key by the time downgrade
      runs, so leaving the data clean is the right behaviour.
    """
    op.drop_index("ix_factors_last_seen_job_id", table_name="factors")
    op.drop_constraint("fk_factors_last_seen_job_id", "factors", type_="foreignkey")
    op.drop_column("factors", "last_seen_job_id")
    op.execute("DROP INDEX IF EXISTS uq_factor_identity_no_year")
    op.execute("DROP INDEX IF EXISTS uq_factor_identity")
    op.alter_column(
        "factors",
        "classification",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="classification::json",
    )
