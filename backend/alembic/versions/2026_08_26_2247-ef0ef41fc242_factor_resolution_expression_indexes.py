# codeql[py/unused-global-variable]
"""factor resolution expression indexes

Revision ID: ef0ef41fc242
Revises: a62060da49c0
Create Date: 2026-08-26 22:47:43.649113

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "ef0ef41fc242"  # noqa: F841
down_revision: str | Sequence[str] | None = "a62060da49c0"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # if_not_exists: dev already carries hand-created copies of several of
    # these from the #2404 experiment -- adopt, don't fail. Autogenerate also
    # proposed unrelated carbon_projects/carbon_reports changes (local-DB
    # drift); pruned per the guardrails.
    op.create_index(
        "ix_factors_res_building_name",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'building_name')"),
        ],
        unique=False,
        postgresql_where=sa.text("(classification->>'building_name') IS NOT NULL"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_factors_res_category",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'category')"),
        ],
        unique=False,
        postgresql_where=sa.text("(classification->>'category') IS NOT NULL"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_factors_res_equipment_class",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'equipment_class')"),
        ],
        unique=False,
        postgresql_where=sa.text("(classification->>'equipment_class') IS NOT NULL"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_factors_res_name",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'name')"),
        ],
        unique=False,
        postgresql_where=sa.text("(classification->>'name') IS NOT NULL"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_factors_res_provider",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'provider')"),
        ],
        unique=False,
        postgresql_where=sa.text("(classification->>'provider') IS NOT NULL"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_factors_res_purchase_category",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'purchase_category')"),
        ],
        unique=False,
        postgresql_where=sa.text("(classification->>'purchase_category') IS NOT NULL"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_factors_res_purchase_institutional_code",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'purchase_institutional_code')"),
        ],
        unique=False,
        postgresql_where=sa.text(
            "(classification->>'purchase_institutional_code') IS NOT NULL"
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_factors_res_researchfacility_id",
        "factors",
        [
            "data_entry_type_id",
            "year",
            sa.literal_column("(classification->>'researchfacility_id')"),
        ],
        unique=False,
        postgresql_where=sa.text(
            "(classification->>'researchfacility_id') IS NOT NULL"
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_factors_res_researchfacility_id",
        table_name="factors",
        postgresql_where=sa.text(
            "(classification->>'researchfacility_id') IS NOT NULL"
        ),
        if_exists=True,
    )
    op.drop_index(
        "ix_factors_res_purchase_institutional_code",
        table_name="factors",
        postgresql_where=sa.text(
            "(classification->>'purchase_institutional_code') IS NOT NULL"
        ),
        if_exists=True,
    )
    op.drop_index(
        "ix_factors_res_purchase_category",
        table_name="factors",
        postgresql_where=sa.text("(classification->>'purchase_category') IS NOT NULL"),
        if_exists=True,
    )
    op.drop_index(
        "ix_factors_res_provider",
        table_name="factors",
        postgresql_where=sa.text("(classification->>'provider') IS NOT NULL"),
        if_exists=True,
    )
    op.drop_index(
        "ix_factors_res_name",
        table_name="factors",
        postgresql_where=sa.text("(classification->>'name') IS NOT NULL"),
        if_exists=True,
    )
    op.drop_index(
        "ix_factors_res_equipment_class",
        table_name="factors",
        postgresql_where=sa.text("(classification->>'equipment_class') IS NOT NULL"),
        if_exists=True,
    )
    op.drop_index(
        "ix_factors_res_category",
        table_name="factors",
        postgresql_where=sa.text("(classification->>'category') IS NOT NULL"),
        if_exists=True,
    )
    op.drop_index(
        "ix_factors_res_building_name",
        table_name="factors",
        postgresql_where=sa.text("(classification->>'building_name') IS NOT NULL"),
        if_exists=True,
    )
