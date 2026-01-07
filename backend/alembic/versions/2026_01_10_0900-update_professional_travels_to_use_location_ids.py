"""update professional_travels to use location_ids and add emissions table

Revision ID: 1c3ba772940b
Revises: bbc28e5f3765
Create Date: 2026-01-10 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from sqlalchemy import JSON, TIMESTAMP, inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c3ba772940b"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "bbc28e5f3765"  # noqa: F841 - revises remove_country_and_factor_type_from_train_impact_factors
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create professional_travel_emissions table first (if it doesn't exist)
    if "professional_travel_emissions" not in existing_tables:
        op.create_table(
            "professional_travel_emissions",
            sa.Column(
                "professional_travel_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "distance_km",
                sa.Float(),
                nullable=False,
            ),
            sa.Column(
                "kg_co2eq",
                sa.Float(),
                nullable=False,
            ),
            sa.Column(
                "plane_impact_factor_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "train_impact_factor_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "formula_version",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="v1",
            ),
            sa.Column(
                "computed_at",
                TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "calculation_inputs",
                JSON,
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column(
                "is_current",
                sa.Boolean(),
                nullable=False,
                server_default="1",
            ),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["professional_travel_id"],
                ["professional_travels.id"],
            ),
            sa.ForeignKeyConstraint(
                ["plane_impact_factor_id"],
                ["plane_impact_factors.id"],
            ),
            sa.ForeignKeyConstraint(
                ["train_impact_factor_id"],
                ["train_impact_factors.id"],
            ),
        )

        # Create indexes for professional_travel_emissions
        op.create_index(
            op.f("ix_professional_travel_emissions_professional_travel_id"),
            "professional_travel_emissions",
            ["professional_travel_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travel_emissions_plane_impact_factor_id"),
            "professional_travel_emissions",
            ["plane_impact_factor_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travel_emissions_train_impact_factor_id"),
            "professional_travel_emissions",
            ["train_impact_factor_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travel_emissions_is_current"),
            "professional_travel_emissions",
            ["is_current"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travel_emissions_computed_at"),
            "professional_travel_emissions",
            ["computed_at"],
            unique=False,
        )

    # Get existing columns once for reuse
    existing_columns = [
        col["name"] for col in inspector.get_columns("professional_travels")
    ]

    # 2. Add new location_id columns to professional_travels (nullable for migration)
    if "origin_location_id" not in existing_columns:
        op.add_column(
            "professional_travels",
            sa.Column(
                "origin_location_id",
                sa.Integer(),
                nullable=True,  # Make nullable initially for data migration
            ),
        )
    if "destination_location_id" not in existing_columns:
        op.add_column(
            "professional_travels",
            sa.Column(
                "destination_location_id",
                sa.Integer(),
                nullable=True,  # Make nullable initially for data migration
            ),
        )

    # 3. Create indexes for new foreign key columns
    existing_indexes = [
        idx["name"] for idx in inspector.get_indexes("professional_travels")
    ]

    if "ix_professional_travels_origin_location_id" not in existing_indexes:
        op.create_index(
            op.f("ix_professional_travels_origin_location_id"),
            "professional_travels",
            ["origin_location_id"],
            unique=False,
        )
    if "ix_professional_travels_destination_location_id" not in existing_indexes:
        op.create_index(
            op.f("ix_professional_travels_destination_location_id"),
            "professional_travels",
            ["destination_location_id"],
            unique=False,
        )

    # 4. Add foreign key constraints (check if they exist first)
    fk_constraints = [
        fk["name"] for fk in inspector.get_foreign_keys("professional_travels")
    ]

    if "fk_professional_travels_origin_location_id" not in fk_constraints:
        op.create_foreign_key(
            "fk_professional_travels_origin_location_id",
            "professional_travels",
            "locations",
            ["origin_location_id"],
            ["id"],
        )
    if "fk_professional_travels_destination_location_id" not in fk_constraints:
        op.create_foreign_key(
            "fk_professional_travels_destination_location_id",
            "professional_travels",
            "locations",
            ["destination_location_id"],
            ["id"],
        )

    # 5. Migrate data: This would need to lookup location IDs from names
    # For now, we leave it nullable. The application logic should handle
    # data migration separately or during seed.
    # NOTE: You may want to add a data migration script here that:
    # - Looks up locations by name in the locations table
    # - Updates origin_location_id and destination_location_id
    # - If location not found, logs warning or creates a placeholder

    # 6. Drop old columns (origin, destination, distance_km, kg_co2eq)
    # Only drop if columns exist (for safety)
    columns_to_drop = ["origin", "destination", "distance_km", "kg_co2eq"]

    for col_name in columns_to_drop:
        if col_name in existing_columns:
            op.drop_column("professional_travels", col_name)

    # 7. Make location_id columns NOT NULL after data migration
    # Note: Uncomment these after ensuring all rows have valid location_ids
    # op.alter_column(
    #     "professional_travels",
    #     "origin_location_id",
    #     nullable=False,
    # )
    # op.alter_column(
    #     "professional_travels",
    #     "destination_location_id",
    #     nullable=False,
    # )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Re-add old columns
    op.add_column(
        "professional_travels",
        sa.Column(
            "origin",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,  # Nullable for downgrade safety
        ),
    )
    op.add_column(
        "professional_travels",
        sa.Column(
            "destination",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,  # Nullable for downgrade safety
        ),
    )
    op.add_column(
        "professional_travels",
        sa.Column("distance_km", sa.Float(), nullable=True),
    )
    op.add_column(
        "professional_travels",
        sa.Column("kg_co2eq", sa.Float(), nullable=True),
    )

    # 2. Migrate data back from location_ids to names
    # This would need to lookup location names from IDs
    # For now, we just add the columns back as nullable

    # 3. Drop foreign key constraints
    op.drop_constraint(
        "fk_professional_travels_destination_location_id",
        "professional_travels",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_professional_travels_origin_location_id",
        "professional_travels",
        type_="foreignkey",
    )

    # 4. Drop indexes for location_id columns
    op.drop_index(
        op.f("ix_professional_travels_destination_location_id"),
        table_name="professional_travels",
    )
    op.drop_index(
        op.f("ix_professional_travels_origin_location_id"),
        table_name="professional_travels",
    )

    # 5. Drop location_id columns
    op.drop_column("professional_travels", "destination_location_id")
    op.drop_column("professional_travels", "origin_location_id")

    # 6. Drop professional_travel_emissions table
    op.drop_index(
        op.f("ix_professional_travel_emissions_computed_at"),
        table_name="professional_travel_emissions",
    )
    op.drop_index(
        op.f("ix_professional_travel_emissions_is_current"),
        table_name="professional_travel_emissions",
    )
    op.drop_index(
        op.f("ix_professional_travel_emissions_train_impact_factor_id"),
        table_name="professional_travel_emissions",
    )
    op.drop_index(
        op.f("ix_professional_travel_emissions_plane_impact_factor_id"),
        table_name="professional_travel_emissions",
    )
    op.drop_index(
        op.f("ix_professional_travel_emissions_professional_travel_id"),
        table_name="professional_travel_emissions",
    )
    op.drop_table("professional_travel_emissions")
