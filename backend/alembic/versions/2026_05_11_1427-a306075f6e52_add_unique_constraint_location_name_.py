# codeql[py/unused-global-variable]
"""Replace nullable UNIQUE constraint on locations with two partial unique indexes.

Postgres UNIQUE constraints allow multiple NULLs, so the previous
``uq_location_name_mode_country`` constraint did NOT enforce uniqueness when
``country_code IS NULL``.

Replace it with:
  - ``uix_location_name_mode_country_notnull``  WHERE country_code IS NOT NULL
      → true uniqueness for the normal case (named country)
  - ``uix_location_name_mode_null_country``      WHERE country_code IS NULL
      → at most one row per (name, transport_mode) when country is unknown

Revision ID: a306075f6e52
Revises: 1e56d303cc85
Create Date: 2026-05-11 14:27:33.046455

"""

from typing import Sequence, Union

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "a306075f6e52"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "1e56d303cc85"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Replace nullable UNIQUE constraint with two partial unique indexes."""
    op.drop_constraint("uq_location_name_mode_country", "locations", type_="unique")

    # Enforce uniqueness when country_code is present (the common path).
    op.create_index(
        "uix_location_name_mode_country_notnull",
        "locations",
        ["name", "transport_mode", "country_code"],
        unique=True,
        postgresql_where="country_code IS NOT NULL",
    )

    # Prevent duplicate (name, transport_mode) rows that both lack a country_code.
    op.create_index(
        "uix_location_name_mode_null_country",
        "locations",
        ["name", "transport_mode"],
        unique=True,
        postgresql_where="country_code IS NULL",
    )


def downgrade() -> None:
    """Restore the original (ineffective-for-NULLs) UNIQUE constraint."""
    op.drop_index(
        "uix_location_name_mode_null_country",
        table_name="locations",
        postgresql_where="country_code IS NULL",
    )
    op.drop_index(
        "uix_location_name_mode_country_notnull",
        table_name="locations",
        postgresql_where="country_code IS NOT NULL",
    )
    op.create_unique_constraint(
        "uq_location_name_mode_country",
        "locations",
        ["name", "transport_mode", "country_code"],
    )
