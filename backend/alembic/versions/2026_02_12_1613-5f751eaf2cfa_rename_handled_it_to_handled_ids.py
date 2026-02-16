# codeql[py/unused-global-variable]
"""rename handled_it_to_handled_ids

Revision ID: 5f751eaf2cfa
Revises: eeee4be3b6e1
Create Date: 2026-02-12 16:13:57.557555

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
revision: str = "5f751eaf2cfa"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "eeee4be3b6e1"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create the enum type
    op.execute(
        "CREATE TYPE audit_change_type_enum AS ENUM "
        "('CREATE', 'READ', 'UPDATE', 'DELETE', 'ROLLBACK', 'TRANSFER')"
    )

    # Step 2: Rename column handled_it to handled_ids
    op.alter_column(
        "audit_documents",
        "handled_it",
        new_column_name="handled_ids",
        existing_type=sa.JSON(),
        existing_nullable=True,
    )

    # Step 3: Convert change_type from VARCHAR to ENUM with explicit USING clause
    op.execute(
        "ALTER TABLE audit_documents ALTER COLUMN change_type "
        "TYPE audit_change_type_enum USING change_type::audit_change_type_enum"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Step 1: Convert change_type back from ENUM to VARCHAR
    op.execute(
        "ALTER TABLE audit_documents ALTER COLUMN change_type TYPE "
        "VARCHAR USING change_type::text"
    )

    # Step 2: Rename column handled_ids back to handled_it
    op.alter_column(
        "audit_documents",
        "handled_ids",
        new_column_name="handled_it",
        existing_type=sa.JSON(),
        existing_nullable=True,
    )

    # Step 3: Drop the enum type
    op.execute("DROP TYPE audit_change_type_enum")
