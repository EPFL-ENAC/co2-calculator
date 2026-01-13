"""seed-data

Revision ID: b0c5eadb058f
Revises: 84a925e8d8e8
Create Date: 2026-01-12 17:09:38.586726

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b0c5eadb058f"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "84a925e8d8e8"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # ==========================================================================
    # MODULE_TYPES
    # Matching frontend MODULES constant and ModuleTypeId enum
    # ==========================================================================
    op.execute(
        """
        INSERT INTO module_types (id, name, description) VALUES
        (1, 'my-lab', 'Headcount and lab personnel'),
        (2, 'professional-travel', 'Professional travel and transport'),
        (3, 'infrastructure', 'Building and infrastructure'),
        (4, 'equipment-electric-consumption', 'Equipment electricity consumption'),
        (5, 'purchase', 'Purchases and procurement'),
        (6, 'internal-services', 'Internal EPFL services'),
        (7, 'external-cloud', 'External cloud services'),
        (99, 'global', 'Global reference data (not a real module)')
        """
    )

    # ==========================================================================
    # DATA_ENTRY_TYPES
    # Subcategories within each module type
    # ==========================================================================
    op.execute(
        """
        INSERT INTO data_entry_types (id, name, description, module_type_id) VALUES
        -- MyLab (module_type_id=1) - Headcount variants
        (1, 'member', 'Staff members', 1),
        (2, 'student', 'Students (Bachelor, Master, PhD)', 1),
        
        -- Equipment (module_type_id=4) - Equipment variants
        (9, 'scientific', 'Scientific/laboratory equipment', 4),
        (10, 'it', 'IT equipment (computers, servers)', 4),
        (11, 'admin', 'Administrative equipment', 4),
        
        -- Professional Travel (module_type_id=2) - Travel variants
        (20, 'flight', 'Air travel', 2),
        (21, 'train', 'Train travel', 2),
        (22, 'car', 'Car travel', 2),
        
        -- Infrastructure (module_type_id=3) - Building variants
        (30, 'building', 'Building emissions', 3),
        
        -- Global/special types for factors
        (100, 'energy_mix', 'Energy mix factors (emission factors)', 99)
        """
    )

    # ==========================================================================
    # EMISSION_TYPES
    # Categories for emission calculations
    # Note: 'energy' is a generic conversion type used by emission factors
    # ==========================================================================
    op.execute(
        """
        INSERT INTO emission_types (id, code, description) VALUES
        (1, 'energy', 'Generic energy conversion (kWh to kgCO2eq) - used by emission factors'),
        (2, 'equipment', 'Equipment electricity consumption emissions'),
        (3, 'food', 'Food-related emissions (catering, meals)'),
        (4, 'waste', 'Waste disposal emissions'),
        (5, 'transport', 'Commuting and transport emissions'),
        (6, 'grey_energy', 'Embodied energy in materials and infrastructure'),
        (7, 'flight', 'Air travel emissions'),
        (8, 'train', 'Train travel emissions'),
        (9, 'car', 'Car travel emissions')
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Clear seed data
    op.execute("DELETE FROM emission_types")
    op.execute("DELETE FROM data_entry_types")
    op.execute("DELETE FROM module_types")
