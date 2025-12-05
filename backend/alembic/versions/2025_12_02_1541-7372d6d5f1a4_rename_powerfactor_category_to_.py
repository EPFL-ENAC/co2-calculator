"""rename_powerfactor_category_to_submodule_and_add_equipment_submodule

Revision ID: 7372d6d5f1a4
Revises: 4bead03d8536
Create Date: 2025-12-02 15:41:16.088369

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7372d6d5f1a4"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "4bead03d8536"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Rename power_factors.category to power_factors.submodule
    op.alter_column(
        "power_factors",
        "category",
        new_column_name="submodule",
        existing_type=sa.String(),
        existing_nullable=False,
    )

    # Add equipment.submodule column
    op.add_column(
        "equipment",
        sa.Column("submodule", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    # Create index on equipment.submodule
    op.create_index(
        op.f("ix_equipment_submodule"), "equipment", ["submodule"], unique=False
    )

    # Note: We're allowing nullable=True initially for the migration
    # The seed script will populate values


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index on equipment.submodule
    op.drop_index(op.f("ix_equipment_submodule"), table_name="equipment")

    # Remove equipment.submodule column
    op.drop_column("equipment", "submodule")

    # Rename power_factors.submodule back to power_factors.category
    op.alter_column(
        "power_factors",
        "submodule",
        new_column_name="category",
        existing_type=sa.String(),
        existing_nullable=False,
    )
