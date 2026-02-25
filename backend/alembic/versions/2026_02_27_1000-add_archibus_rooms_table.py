# codeql[py/unused-global-variable]
"""add archibus_rooms table

Revision ID: b1e2f3a4d5c6
Revises: c7d9a1b2e3f4
Create Date: 2026-02-20 10:00:00.000000

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
revision: str = "b1e2f3a4d5c6"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "91ea7e3ff1ee"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    op.create_table(
        "archibus_rooms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("unit_institutional_id", sa.VARCHAR(), nullable=True),
        sa.Column("building_location", sa.VARCHAR(), nullable=False),
        sa.Column("building_name", sa.VARCHAR(), nullable=False),
        sa.Column("room_name", sa.VARCHAR(), nullable=False),
        sa.Column("room_type", sa.VARCHAR(), nullable=True),
        sa.Column("room_surface_square_meter", sa.Float(), nullable=True),
        sa.Column("heating_kwh_per_square_meter", sa.Float(), nullable=True),
        sa.Column("cooling_kwh_per_square_meter", sa.Float(), nullable=True),
        sa.Column("ventilation_kwh_per_square_meter", sa.Float(), nullable=True),
        sa.Column("lighting_kwh_per_square_meter", sa.Float(), nullable=True),
        sa.Column("note", sa.VARCHAR(), nullable=True),
        sa.Column("kg_co2eq", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
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


def downgrade() -> None:
    op.drop_index(op.f("ix_archibus_rooms_room_name"), table_name="archibus_rooms")
    op.drop_index(op.f("ix_archibus_rooms_building_name"), table_name="archibus_rooms")
    op.drop_index(
        op.f("ix_archibus_rooms_building_location"), table_name="archibus_rooms"
    )
    op.drop_index(
        op.f("ix_archibus_rooms_unit_institutional_id"), table_name="archibus_rooms"
    )
    op.drop_index(op.f("ix_archibus_rooms_id"), table_name="archibus_rooms")
    op.drop_table("archibus_rooms")
