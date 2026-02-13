# codeql[py/unused-global-variable]
"""change audit changed_by to integer

Revision ID: c7d9a1b2e3f4
Revises: a1b2c3d4e5f6
Create Date: 2026-02-13 12:30:00.000000

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


# revision identifiers, used by Alembic.
revision: str = "c7d9a1b2e3f4"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE audit_documents SET changed_by = NULL "
            "WHERE changed_by IS NOT NULL AND changed_by !~ '^[0-9]+$'"
        )
        op.execute(
            "ALTER TABLE audit_documents ALTER COLUMN changed_by "
            "TYPE INTEGER USING changed_by::integer"
        )
        op.execute("ALTER TABLE audit_documents ALTER COLUMN changed_by DROP NOT NULL")
    else:
        op.execute(
            "UPDATE audit_documents SET changed_by = NULL "
            "WHERE changed_by IS NOT NULL AND changed_by NOT GLOB '[0-9]*'"
        )
        with op.batch_alter_table("audit_documents") as batch:
            batch.alter_column(
                "changed_by",
                existing_type=sa.String(),
                type_=sa.Integer(),
                nullable=True,
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE audit_documents ALTER COLUMN changed_by "
            "TYPE VARCHAR USING changed_by::text"
        )
        op.execute(
            "UPDATE audit_documents SET changed_by = 'unknown' WHERE changed_by IS NULL"
        )
        op.execute("ALTER TABLE audit_documents ALTER COLUMN changed_by SET NOT NULL")
    else:
        with op.batch_alter_table("audit_documents") as batch:
            batch.alter_column(
                "changed_by",
                existing_type=sa.Integer(),
                type_=sa.String(),
                nullable=True,
            )
        op.execute(
            "UPDATE audit_documents SET changed_by = 'unknown' "
            "WHERE changed_by IS NULL OR changed_by = ''"
        )
        with op.batch_alter_table("audit_documents") as batch:
            batch.alter_column(
                "changed_by",
                existing_type=sa.String(),
                nullable=False,
            )
