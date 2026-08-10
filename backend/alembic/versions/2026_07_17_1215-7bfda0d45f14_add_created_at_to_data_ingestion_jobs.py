# codeql[py/unused-global-variable]
"""add created_at to data_ingestion_jobs

Revision ID: 7bfda0d45f14
Revises: 3f1c7a94be2e
Create Date: 2026-07-17 12:15:49.510720

"""

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
revision: str = "7bfda0d45f14"  # noqa: F841
down_revision: str | Sequence[str] | None = "3f1c7a94be2e"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # False-positive drop_index on uq_active_datasource_per_module pruned
    # (partial unique index lives outside SQLModel metadata).
    op.add_column(
        "data_ingestion_jobs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("data_ingestion_jobs", "created_at")
