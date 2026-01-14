"""merged professional travel module migrations

Revision ID: merged_travel_001
Revises: 99bb31e235b5
Create Date: 2026-01-15 12:00:00.000000

This migration merges the following migrations:
- create professional_travels table
- create locations table
- add countrycode to locations
- create travel impact factors tables
- add min/max distance to plane impact factors
- remove country and factor_type from train impact factors
- update professional_travels to use location_ids and add emissions table
- make traveler_id nullable in professional_travels
- remove return_date from professional_travels

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from sqlalchemy import JSON, TIMESTAMP, inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "merged_travel_001"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "99bb31e235b5"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create locations table (with countrycode already included)
    if "locations" not in existing_tables:
        op.create_table(
            "locations",
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "transport_mode",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=False,
            ),
            sa.Column(
                "name",
                sqlmodel.sql.sqltypes.AutoString(length=255),
                nullable=False,
            ),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column(
                "iata_code",
                sqlmodel.sql.sqltypes.AutoString(length=10),
                nullable=True,
            ),
            sa.Column(
                "countrycode",
                sqlmodel.sql.sqltypes.AutoString(length=10),
                nullable=True,
            ),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        # Create indexes for locations
        op.create_index(
            op.f("ix_locations_created_by"),
            "locations",
            ["created_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_locations_iata_code"),
            "locations",
            ["iata_code"],
            unique=False,
        )
        op.create_index(
            op.f("ix_locations_name"),
            "locations",
            ["name"],
            unique=False,
        )
        op.create_index(
            op.f("ix_locations_transport_mode"),
            "locations",
            ["transport_mode"],
            unique=False,
        )
        op.create_index(
            op.f("ix_locations_updated_by"),
            "locations",
            ["updated_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_locations_countrycode"),
            "locations",
            ["countrycode"],
            unique=False,
        )

    # 2. Create plane_impact_factors table (with min/max_distance already included)
    if "plane_impact_factors" not in existing_tables:
        op.create_table(
            "plane_impact_factors",
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "factor_type",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=False,
            ),
            sa.Column(
                "category",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=False,
            ),
            sa.Column("impact_score", sa.Float(), nullable=False),
            sa.Column("rfi_adjustment", sa.Float(), nullable=False),
            sa.Column("min_distance", sa.Float(), nullable=True),
            sa.Column("max_distance", sa.Float(), nullable=True),
            sa.Column(
                "valid_from",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "valid_to",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        # Create indexes for plane_impact_factors
        op.create_index(
            op.f("ix_plane_impact_factors_created_by"),
            "plane_impact_factors",
            ["created_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_plane_impact_factors_factor_type"),
            "plane_impact_factors",
            ["factor_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_plane_impact_factors_category"),
            "plane_impact_factors",
            ["category"],
            unique=False,
        )
        op.create_index(
            op.f("ix_plane_impact_factors_updated_by"),
            "plane_impact_factors",
            ["updated_by"],
            unique=False,
        )

    # 3. Create train_impact_factors table (without factor_type and country columns)
    if "train_impact_factors" not in existing_tables:
        op.create_table(
            "train_impact_factors",
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "countrycode",
                sqlmodel.sql.sqltypes.AutoString(length=10),
                nullable=False,
            ),
            sa.Column("impact_score", sa.Float(), nullable=False),
            sa.Column(
                "valid_from",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "valid_to",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        # Create indexes for train_impact_factors
        op.create_index(
            op.f("ix_train_impact_factors_created_by"),
            "train_impact_factors",
            ["created_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_train_impact_factors_countrycode"),
            "train_impact_factors",
            ["countrycode"],
            unique=False,
        )
        op.create_index(
            op.f("ix_train_impact_factors_updated_by"),
            "train_impact_factors",
            ["updated_by"],
            unique=False,
        )

    # 4. Create professional_travels table
    # (with traveler_id nullable, without return_date,
    #  with origin_location_id and destination_location_id)
    if "professional_travels" not in existing_tables:
        op.create_table(
            "professional_travels",
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "traveler_id",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=True,  # Nullable from the start
            ),
            sa.Column(
                "traveler_name",
                sqlmodel.sql.sqltypes.AutoString(length=255),
                nullable=False,
            ),
            sa.Column(
                "origin_location_id",
                sa.Integer(),
                nullable=True,  # Nullable for data migration
            ),
            sa.Column(
                "destination_location_id",
                sa.Integer(),
                nullable=True,  # Nullable for data migration
            ),
            sa.Column("departure_date", sa.Date(), nullable=True),
            sa.Column(
                "is_round_trip", sa.Boolean(), nullable=False, server_default="0"
            ),
            sa.Column(
                "transport_mode",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=False,
            ),
            sa.Column(
                "class", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True
            ),
            sa.Column(
                "number_of_trips", sa.Integer(), nullable=False, server_default="1"
            ),
            sa.Column(
                "unit_id", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False
            ),
            sa.Column(
                "provider", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True
            ),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["origin_location_id"],
                ["locations.id"],
            ),
            sa.ForeignKeyConstraint(
                ["destination_location_id"],
                ["locations.id"],
            ),
        )
        # Create indexes for professional_travels
        op.create_index(
            op.f("ix_professional_travels_created_by"),
            "professional_travels",
            ["created_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travels_unit_id"),
            "professional_travels",
            ["unit_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travels_updated_by"),
            "professional_travels",
            ["updated_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travels_year"),
            "professional_travels",
            ["year"],
            unique=False,
        )
        op.create_index(
            "ix_professional_travels_unit_id_year",
            "professional_travels",
            ["unit_id", "year"],
            unique=False,
        )
        op.create_index(
            "ix_professional_travels_traveler_id",
            "professional_travels",
            ["traveler_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travels_origin_location_id"),
            "professional_travels",
            ["origin_location_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_professional_travels_destination_location_id"),
            "professional_travels",
            ["destination_location_id"],
            unique=False,
        )

    # 5. Create professional_travel_emissions table
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


def downgrade() -> None:
    """Downgrade schema."""
    # Drop professional_travel_emissions table
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

    # Drop professional_travels table
    op.drop_index(
        "ix_professional_travels_traveler_id", table_name="professional_travels"
    )
    op.drop_index(
        "ix_professional_travels_unit_id_year", table_name="professional_travels"
    )
    op.drop_index(
        op.f("ix_professional_travels_year"), table_name="professional_travels"
    )
    op.drop_index(
        op.f("ix_professional_travels_updated_by"), table_name="professional_travels"
    )
    op.drop_index(
        op.f("ix_professional_travels_unit_id"), table_name="professional_travels"
    )
    op.drop_index(
        op.f("ix_professional_travels_origin_location_id"),
        table_name="professional_travels",
    )
    op.drop_index(
        op.f("ix_professional_travels_destination_location_id"),
        table_name="professional_travels",
    )
    op.drop_index(
        op.f("ix_professional_travels_created_by"), table_name="professional_travels"
    )
    op.drop_table("professional_travels")

    # Drop train_impact_factors table
    op.drop_index(
        op.f("ix_train_impact_factors_updated_by"), table_name="train_impact_factors"
    )
    op.drop_index(
        op.f("ix_train_impact_factors_countrycode"), table_name="train_impact_factors"
    )
    op.drop_index(
        op.f("ix_train_impact_factors_created_by"), table_name="train_impact_factors"
    )
    op.drop_table("train_impact_factors")

    # Drop plane_impact_factors table
    op.drop_index(
        op.f("ix_plane_impact_factors_updated_by"), table_name="plane_impact_factors"
    )
    op.drop_index(
        op.f("ix_plane_impact_factors_category"), table_name="plane_impact_factors"
    )
    op.drop_index(
        op.f("ix_plane_impact_factors_factor_type"), table_name="plane_impact_factors"
    )
    op.drop_index(
        op.f("ix_plane_impact_factors_created_by"), table_name="plane_impact_factors"
    )
    op.drop_table("plane_impact_factors")

    # Drop locations table
    op.drop_index(op.f("ix_locations_updated_by"), table_name="locations")
    op.drop_index(op.f("ix_locations_transport_mode"), table_name="locations")
    op.drop_index(op.f("ix_locations_name"), table_name="locations")
    op.drop_index(op.f("ix_locations_iata_code"), table_name="locations")
    op.drop_index(op.f("ix_locations_countrycode"), table_name="locations")
    op.drop_index(op.f("ix_locations_created_by"), table_name="locations")
    op.drop_table("locations")
