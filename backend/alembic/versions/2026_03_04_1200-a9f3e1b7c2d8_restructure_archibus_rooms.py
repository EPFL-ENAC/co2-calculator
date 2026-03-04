# codeql[py/unused-global-variable]
"""restructure archibus_rooms:
drop energy columns, drop unit_institutional_id, rename to building_rooms

Revision ID: a9f3e1b7c2d8
Revises: bb5495fde09c
Create Date: 2026-03-04 12:00:00.000000

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
revision: str = "a9f3e1b7c2d8"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "bb5495fde09c"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    # 1. Drop removed columns (and unit index)
    op.drop_index(
        op.f("ix_archibus_rooms_unit_institutional_id"),
        table_name="archibus_rooms",
        if_exists=True,
    )
    op.drop_column("archibus_rooms", "unit_institutional_id")
    op.drop_column("archibus_rooms", "heating_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "cooling_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "ventilation_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "lighting_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "note")
    op.drop_column("archibus_rooms", "kg_co2eq")

    # 2. Rename table
    op.rename_table("archibus_rooms", "building_rooms")

    # 3. Rename remaining indexes to match new table name
    op.execute("ALTER INDEX ix_archibus_rooms_id RENAME TO ix_building_rooms_id")
    op.execute(
        "ALTER INDEX ix_archibus_rooms_building_location "
        "RENAME TO ix_building_rooms_building_location"
    )
    op.execute(
        "ALTER INDEX ix_archibus_rooms_building_name "
        "RENAME TO ix_building_rooms_building_name"
    )
    op.execute(
        "ALTER INDEX ix_archibus_rooms_room_name RENAME TO ix_building_rooms_room_name"
    )


def downgrade() -> None:
    # 1. Rename table back
    op.rename_table("building_rooms", "archibus_rooms")

    # 2. Rename indexes back
    op.execute("ALTER INDEX ix_building_rooms_id RENAME TO ix_archibus_rooms_id")
    op.execute(
        "ALTER INDEX ix_building_rooms_building_location "
        "RENAME TO ix_archibus_rooms_building_location"
    )
    op.execute(
        "ALTER INDEX ix_building_rooms_building_name "
        "RENAME TO ix_archibus_rooms_building_name"
    )
    op.execute(
        "ALTER INDEX ix_building_rooms_room_name RENAME TO ix_archibus_rooms_room_name"
    )

    # 3. Re-add removed columns
    op.add_column("archibus_rooms", sa.Column("kg_co2eq", sa.Float(), nullable=True))
    op.add_column("archibus_rooms", sa.Column("note", sa.VARCHAR(), nullable=True))
    op.add_column(
        "archibus_rooms",
        sa.Column("lighting_kwh_per_square_meter", sa.Float(), nullable=True),
    )
    op.add_column(
        "archibus_rooms",
        sa.Column("ventilation_kwh_per_square_meter", sa.Float(), nullable=True),
    )
    op.add_column(
        "archibus_rooms",
        sa.Column("cooling_kwh_per_square_meter", sa.Float(), nullable=True),
    )
    op.add_column(
        "archibus_rooms",
        sa.Column("heating_kwh_per_square_meter", sa.Float(), nullable=True),
    )
    op.add_column(
        "archibus_rooms",
        sa.Column("unit_institutional_id", sa.VARCHAR(), nullable=True),
    )
    op.create_index(
        op.f("ix_archibus_rooms_unit_institutional_id"),
        "archibus_rooms",
        ["unit_institutional_id"],
        unique=False,
    )
