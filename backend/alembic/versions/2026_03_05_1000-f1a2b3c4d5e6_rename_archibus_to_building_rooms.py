# codeql[py/unused-global-variable]
"""rename archibus_rooms to building_rooms and drop unused columns

Revision ID: f1a2b3c4d5e6
Revises: bb5495fde09c
Create Date: 2026-03-05 10:00:00.000000

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
revision: str = "f1a2b3c4d5e6"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "bb5495fde09c"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    # Drop old indexes on archibus_rooms
    op.drop_index(op.f("ix_archibus_rooms_room_name"), table_name="archibus_rooms")
    op.drop_index(op.f("ix_archibus_rooms_building_name"), table_name="archibus_rooms")
    op.drop_index(
        op.f("ix_archibus_rooms_building_location"), table_name="archibus_rooms"
    )
    op.drop_index(
        op.f("ix_archibus_rooms_unit_institutional_id"), table_name="archibus_rooms"
    )
    op.drop_index(op.f("ix_archibus_rooms_id"), table_name="archibus_rooms")

    # Drop unused columns
    op.drop_column("archibus_rooms", "unit_institutional_id")
    op.drop_column("archibus_rooms", "heating_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "cooling_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "ventilation_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "lighting_kwh_per_square_meter")
    op.drop_column("archibus_rooms", "note")
    op.drop_column("archibus_rooms", "kg_co2eq")

    # Rename table
    op.rename_table("archibus_rooms", "building_rooms")

    # Recreate indexes on building_rooms
    op.create_index(
        op.f("ix_building_rooms_id"), "building_rooms", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_building_rooms_building_location"),
        "building_rooms",
        ["building_location"],
        unique=False,
    )
    op.create_index(
        op.f("ix_building_rooms_building_name"),
        "building_rooms",
        ["building_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_building_rooms_room_name"),
        "building_rooms",
        ["room_name"],
        unique=False,
    )


def downgrade() -> None:
    # Drop new indexes
    op.drop_index(op.f("ix_building_rooms_room_name"), table_name="building_rooms")
    op.drop_index(op.f("ix_building_rooms_building_name"), table_name="building_rooms")
    op.drop_index(
        op.f("ix_building_rooms_building_location"), table_name="building_rooms"
    )
    op.drop_index(op.f("ix_building_rooms_id"), table_name="building_rooms")

    # Rename back
    op.rename_table("building_rooms", "archibus_rooms")

    # Restore dropped columns
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

    # Restore old indexes
    op.create_index(
        op.f("ix_archibus_rooms_id"), "archibus_rooms", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_archibus_rooms_unit_institutional_id"),
        "archibus_rooms",
        ["unit_institutional_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archibus_rooms_building_location"),
        "archibus_rooms",
        ["building_location"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archibus_rooms_building_name"),
        "archibus_rooms",
        ["building_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archibus_rooms_room_name"),
        "archibus_rooms",
        ["room_name"],
        unique=False,
    )
