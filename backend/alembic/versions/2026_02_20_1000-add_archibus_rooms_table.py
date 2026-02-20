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
down_revision: Union[str, Sequence[str], None] = "c7d9a1b2e3f4"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    op.create_table(
        "archibus_rooms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("building_name", sa.VARCHAR(), nullable=False),
        sa.Column("building_code", sa.VARCHAR(), nullable=False),
        sa.Column("room_code", sa.VARCHAR(), nullable=False),
        sa.Column("room_name", sa.VARCHAR(), nullable=False),
        sa.Column("generic_type_din", sa.VARCHAR(), nullable=False),
        sa.Column("sia_type", sa.VARCHAR(), nullable=False),
        sa.Column("surface_m2", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_archibus_rooms_id"), "archibus_rooms", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_archibus_rooms_building_name"),
        "archibus_rooms",
        ["building_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archibus_rooms_building_code"),
        "archibus_rooms",
        ["building_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archibus_rooms_room_code"),
        "archibus_rooms",
        ["room_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_archibus_rooms_room_code"), table_name="archibus_rooms")
    op.drop_index(op.f("ix_archibus_rooms_building_code"), table_name="archibus_rooms")
    op.drop_index(op.f("ix_archibus_rooms_building_name"), table_name="archibus_rooms")
    op.drop_index(op.f("ix_archibus_rooms_id"), table_name="archibus_rooms")
    op.drop_table("archibus_rooms")
