# codeql[py/unused-global-variable]
"""migrate data-ingestion

Revision ID: ace5787ef529
Revises: 8d5a01072a3a
Create Date: 2026-03-23 14:09:03.773332

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ace5787ef529"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "8d5a01072a3a"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum types before adding columns
    ingestion_state_enum = postgresql.ENUM(
        "NOT_STARTED", "QUEUED", "RUNNING", "FINISHED", name="ingestion_state_enum"
    )
    ingestion_state_enum.create(op.get_bind(), checkfirst=True)

    ingestion_result_enum = postgresql.ENUM(
        "SUCCESS", "WARNING", "ERROR", name="ingestion_result_enum"
    )
    ingestion_result_enum.create(op.get_bind(), checkfirst=True)

    # Add columns using the created enum types
    op.add_column(
        "data_ingestion_jobs",
        sa.Column(
            "state",
            ingestion_state_enum,
            nullable=True,
        ),
    )
    op.add_column(
        "data_ingestion_jobs",
        sa.Column(
            "result",
            ingestion_result_enum,
            nullable=True,
        ),
    )
    op.drop_column("data_ingestion_jobs", "status")


def downgrade() -> None:
    """Downgrade schema."""
    # Restore the status column
    op.add_column(
        "data_ingestion_jobs",
        sa.Column(
            "status",
            postgresql.ENUM(
                "NOT_STARTED",
                "PENDING",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                name="ingestion_status_enum",
            ),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_column("data_ingestion_jobs", "result")
    op.drop_column("data_ingestion_jobs", "state")

    # Drop enum types
    ingestion_state_enum = postgresql.ENUM(name="ingestion_state_enum")
    ingestion_state_enum.drop(op.get_bind(), checkfirst=True)

    ingestion_result_enum = postgresql.ENUM(name="ingestion_result_enum")
    ingestion_result_enum.drop(op.get_bind(), checkfirst=True)
