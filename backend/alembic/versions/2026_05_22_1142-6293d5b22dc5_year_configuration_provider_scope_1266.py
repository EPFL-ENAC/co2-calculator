# codeql[py/unused-global-variable]
"""year_configuration provider scope (#1266)

Adds ``provider`` to ``year_configuration`` and pivots the PK from
``(year)`` to ``(year, provider)`` so TEST and ACCRED users can each
provision the same year independently.

Existing rows get stamped ``DEFAULT`` via the server default; v0.x drops
the DB between deploys (no backfill until v1.x) so production never
lands on a stamped row.

Autogenerate also detected 7 "removed indexes" (uq_aggregation_active,
uq_emission_recalc_active, uq_factor_identity, uq_factor_identity_no_year,
ix_locations_keywords, ix_pipelines_module_year, ix_pipelines_status) —
all FALSE POSITIVES: those are partial / GIN / raw-SQL indexes declared
in prior migrations but not in the SQLModel metadata, so each fresh
autogenerate offers to drop them.  Stripped from this revision.

Revision ID: 6293d5b22dc5
Revises: c4d5e6f7a8b9
Create Date: 2026-05-22 11:42:31.915898

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
revision: str = "6293d5b22dc5"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "year_configuration",
        sa.Column(
            "provider",
            sa.Enum("ACCRED", "DEFAULT", "TEST", name="user_provider_enum"),
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
    """Downgrade schema.

    After this migration runs, the table can hold multiple rows per
    ``year`` (one per provider). Re-creating a PK on ``year`` alone
    would fail with a duplicate-key error. Drop every non-DEFAULT row
    first so the surviving set is unique on ``year``. v0.x drops the
    DB between deploys, so the data loss is acceptable on a
    downgrade-then-redeploy.
    """
    op.execute("DELETE FROM year_configuration WHERE provider <> 'DEFAULT'")
    op.drop_constraint("year_configuration_pkey", "year_configuration", type_="primary")
    op.create_primary_key("year_configuration_pkey", "year_configuration", ["year"])
    op.drop_column("year_configuration", "provider")
