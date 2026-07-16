# codeql[py/unused-global-variable]
"""Drop auth_exchange_code table (BFF exchange pattern removed).

Revision ID: d88cd2f143bf
Revises: dd2ce8461139
Create Date: 2026-06-29 00:00:00.000000

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
revision: str = "d88cd2f143bf"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "dd2ce8461139"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(
        op.f("ix_auth_exchange_code_user_id"), table_name="auth_exchange_code"
    )
    op.drop_table("auth_exchange_code")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "auth_exchange_code",
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(
        op.f("ix_auth_exchange_code_user_id"),
        "auth_exchange_code",
        ["user_id"],
        unique=False,
    )
