# codeql[py/unused-global-variable]
"""add classification_translations table

Revision ID: b3d9a7e5c1f2
Revises: 95fe938000d4
Create Date: 2026-08-31 18:00:00.000000

"""

from collections.abc import Sequence

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
revision: str = "b3d9a7e5c1f2"  # noqa: F841
down_revision: str | Sequence[str] | None = "95fe938000d4"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841

# Hand-authored (no local Postgres available to run `make db-revision
# --autogenerate` in this sandbox — see PR description). New table only,
# mirrors the shape of the `year_configuration` composite-PK table in the
# initial migration; regenerate/diff against a live DB before merging.


def upgrade() -> None:
    op.create_table(
        "classification_translations",
        sa.Column(
            "field_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "value", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column("lang", sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column(
            "label", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.PrimaryKeyConstraint("field_name", "value", "lang"),
    )


def downgrade() -> None:
    op.drop_table("classification_translations")
