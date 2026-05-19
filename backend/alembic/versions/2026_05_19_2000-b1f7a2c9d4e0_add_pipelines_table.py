# codeql[py/unused-global-variable]
"""add pipelines table (#1236 Phase 1)

First-class pipeline aggregate root.  Table-only: the existing
``data_ingestion_jobs.pipeline_id`` column stays a plain UUID with NO
foreign key here — legacy rows reference pipeline_ids that have no
``pipelines`` row yet, so an enforced FK would reject the first insert.
The FK is added post-backfill in Phase 2
(``ADD CONSTRAINT … NOT VALID`` + ``VALIDATE CONSTRAINT``).

Revision ID: b1f7a2c9d4e0
Revises: 30c096280772
Create Date: 2026-05-19 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


revision: str = "b1f7a2c9d4e0"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "30c096280772"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    op.create_table(
        "pipelines",
        sa.Column("id", sa.UUID(), nullable=False),
        # = the parent job_type (csv_ingest / factor_ingest / unit_sync …)
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="NOT_STARTED",
        ),
        # scope / provenance — int-enum values mirrored from the parent
        sa.Column("entity_type", sa.Integer(), nullable=True),
        sa.Column("ingestion_method", sa.Integer(), nullable=True),
        sa.Column("module_type_id", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("expected_recalc", sa.Integer(), nullable=True),
        sa.Column("job_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipelines_status", "pipelines", ["status"], unique=False)
    op.create_index(
        "ix_pipelines_module_year",
        "pipelines",
        ["module_type_id", "year"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pipelines_module_year", table_name="pipelines")
    op.drop_index("ix_pipelines_status", table_name="pipelines")
    op.drop_table("pipelines")
