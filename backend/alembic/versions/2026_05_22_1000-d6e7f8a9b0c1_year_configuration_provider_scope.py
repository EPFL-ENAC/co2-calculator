# codeql[py/unused-global-variable]
"""year_configuration provider scope (#1266)

Adds a ``provider`` column to ``year_configuration`` and pivots the
primary key from ``(year)`` to ``(year, provider)`` so TEST and ACCRED
users can each provision the same year independently.

Existing rows are stamped ``DEFAULT`` (the dev-fallback value); production
never lands here because v0.x drops the DB between deploys (no backfill
until v1.x).  The server default lets the ALTER COLUMN ... SET NOT NULL
succeed on any pre-existing rows in dev databases.

Revision ID: d6e7f8a9b0c1
Revises: c4d5e6f7a8b9
Create Date: 2026-05-22 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


revision: str = "d6e7f8a9b0c1"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    # The enum type ``user_provider_enum`` already exists (created by the
    # initial migration for ``units`` / ``users`` / ``data_ingestion_jobs``);
    # ``create_type=False`` tells Alembic to reference it, not recreate.
    user_provider_enum = postgresql.ENUM(
        "ACCRED",
        "DEFAULT",
        "TEST",
        name="user_provider_enum",
        create_type=False,
    )
    op.add_column(
        "year_configuration",
        sa.Column(
            "provider",
            user_provider_enum,
            nullable=False,
            server_default="DEFAULT",
        ),
    )
    op.drop_constraint("year_configuration_pkey", "year_configuration", type_="primary")
    op.create_primary_key(
        "year_configuration_pkey",
        "year_configuration",
        ["year", "provider"],
    )


def downgrade() -> None:
    op.drop_constraint("year_configuration_pkey", "year_configuration", type_="primary")
    op.create_primary_key("year_configuration_pkey", "year_configuration", ["year"])
    op.drop_column("year_configuration", "provider")
