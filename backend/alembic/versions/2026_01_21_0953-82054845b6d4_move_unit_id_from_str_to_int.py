"""move unit_id from str to int

Revision ID: 82054845b6d4
Revises: fc5cfc45f96e
Create Date: 2026-01-21 09:53:22.486908

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82054845b6d4"
down_revision: Union[str, Sequence[str], None] = "fc5cfc45f96e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- 1. DROP CONSTRAINTS FIRST ---
    # We must drop Foreign Keys before changing the types of the
    # columns they point to/from.
    op.drop_constraint(
        op.f("emission_factors_created_by_fkey"), "emission_factors", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("equipment_created_by_fkey"), "equipment", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("equipment_updated_by_fkey"), "equipment", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("power_factors_created_by_fkey"), "power_factors", type_="foreignkey"
    )

    # --- 2. ALTER COLUMNS (VARCHAR -> INTEGER) ---
    # We must provide 'postgresql_using' to tell Postgres how to cast String to Int.
    op.alter_column(
        "equipment",
        "unit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="unit_id::integer",
    )
    op.alter_column(
        "headcounts",
        "unit_id",
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="unit_id::integer",
    )
    op.alter_column(
        "inventory",
        "unit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="unit_id::integer",
    )
    op.alter_column(
        "professional_travels",
        "unit_id",
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="unit_id::integer",
    )

    # --- 3. ALTER COLUMNS (INTEGER -> VARCHAR) ---
    # Implicit casting usually works fine here, but explicit is safer.
    op.alter_column(
        "emission_factors",
        "created_by",
        existing_type=sa.INTEGER(),
        type_=sqlmodel.sql.sqltypes.AutoString(),
        existing_nullable=True,
    )
    op.alter_column(
        "equipment",
        "created_by",
        existing_type=sa.INTEGER(),
        type_=sqlmodel.sql.sqltypes.AutoString(),
        existing_nullable=True,
    )
    op.alter_column(
        "equipment",
        "updated_by",
        existing_type=sa.INTEGER(),
        type_=sqlmodel.sql.sqltypes.AutoString(),
        existing_nullable=True,
    )
    op.alter_column(
        "power_factors",
        "created_by",
        existing_type=sa.INTEGER(),
        type_=sqlmodel.sql.sqltypes.AutoString(),
        existing_nullable=True,
    )

    # --- 4. OTHER SCHEMA CHANGES ---

    op.create_index(
        op.f("ix_units_principal_user_provider_code"),
        "units",
        ["principal_user_provider_code"],
        unique=False,
    )
    op.create_foreign_key(
        None, "units", "users", ["principal_user_provider_code"], ["provider_code"]
    )


def downgrade() -> None:
    """Downgrade schema."""

    # 1. CLEANUP UNITS/USERS
    # We remove the ID alter_columns because we removed them from upgrade()
    # Explicitly name the constraint we created in upgrade()
    op.drop_constraint(
        "units_principal_user_provider_code_fkey", "units", type_="foreignkey"
    )
    op.drop_index(op.f("ix_units_principal_user_provider_code"), table_name="units")

    # 2. REVERT unit_id (Integer -> Varchar)
    # Note: Int to Varchar doesn't strictly need 'using', but it's safe to exclude.
    op.alter_column(
        "professional_travels",
        "unit_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory",
        "unit_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "headcounts",
        "unit_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "equipment",
        "unit_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )

    # 3. REVERT created_by/updated_by (Varchar -> Integer) AND RESTORE FKs
    # We MUST use postgresql_using here because we are going from String back to Int

    # Power Factors
    op.alter_column(
        "power_factors",
        "created_by",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        type_=sa.INTEGER(),
        existing_nullable=True,
        postgresql_using="created_by::integer",
    )
    op.create_foreign_key(
        op.f("power_factors_created_by_fkey"),
        "power_factors",
        "users",
        ["created_by"],
        ["id"],
    )

    # Equipment
    op.alter_column(
        "equipment",
        "updated_by",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        type_=sa.INTEGER(),
        existing_nullable=True,
        postgresql_using="updated_by::integer",
    )
    op.alter_column(
        "equipment",
        "created_by",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        type_=sa.INTEGER(),
        existing_nullable=True,
        postgresql_using="created_by::integer",
    )
    op.create_foreign_key(
        op.f("equipment_updated_by_fkey"), "equipment", "users", ["updated_by"], ["id"]
    )
    op.create_foreign_key(
        op.f("equipment_created_by_fkey"), "equipment", "users", ["created_by"], ["id"]
    )

    # Emission Factors
    op.alter_column(
        "emission_factors",
        "created_by",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        type_=sa.INTEGER(),
        existing_nullable=True,
        postgresql_using="created_by::integer",
    )
    op.create_foreign_key(
        op.f("emission_factors_created_by_fkey"),
        "emission_factors",
        "users",
        ["created_by"],
        ["id"],
    )
