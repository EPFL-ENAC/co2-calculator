# codeql[py/unused-global-variable]
"""add pods table

Revision ID: a200b8491d76
Revises: d90884a395e1
Create Date: 2026-06-03 09:17:57.593112

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


# revision identifiers, used by Alembic.
revision: str = "a200b8491d76"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "d90884a395e1"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pods",
        sa.Column(
            "pod_id", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False
        ),
        sa.Column(
            "git_sha", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True
        ),
        sa.Column(
            "app_version", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("pod_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("pods")
