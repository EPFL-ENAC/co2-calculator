"""seed module and variant types

Revision ID: seed_module_variant_types
Revises: ae23fed428b5
Create Date: 2026-01-06 17:00:00.000000

Seeds the module_types and variant_types tables with reference data
matching the frontend MODULES and SUBMODULE_*_TYPES constants.
Uses explicit IDs for FK consistency across environments.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "seed_module_variant_types"
down_revision: Union[str, Sequence[str], None] = "ae23fed428b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed module_types and variant_types reference data."""
    # Insert module_types (7 rows matching frontend MODULES constant)
    # Using explicit IDs for FK consistency
    op.execute("""
        INSERT INTO module_types (id, name, description) VALUES
        (1, 'my-lab', 'Lab members and students headcount'),
        (2, 'professional-travel', 'Professional travel and missions'),
        (3, 'infrastructure', 'Buildings and facilities'),
        (4, 'equipment-electric-consumption', 'Scientific and IT equipment'),
        (5, 'purchase', 'Consumables, durables, and goods'),
        (6, 'internal-services', 'IT support and maintenance services'),
        (7, 'external-cloud', 'Cloud services (SaaS, IaaS, PaaS)')
        ON CONFLICT (id) DO NOTHING;
    """)

    # Insert variant_types (18 rows matching frontend SUBMODULE_*_TYPES constants)
    # Each variant is linked to its parent module_type_id
    op.execute("""
        INSERT INTO variant_types (id, name, description, module_type_id) VALUES
        -- my-lab variants (module_type_id = 1)
        (1, 'member', 'Lab members', 1),
        (2, 'student', 'Students', 1),

        -- professional-travel variants (module_type_id = 2)
        (3, 'conference', 'Conference travel', 2),
        (4, 'fieldwork', 'Fieldwork travel', 2),
        (5, 'training', 'Training travel', 2),
        (6, 'other', 'Other professional travel', 2),

        -- infrastructure variants (module_type_id = 3)
        (7, 'building', 'Buildings', 3),
        (8, 'facility', 'Facilities', 3),

        -- equipment-electric-consumption variants (module_type_id = 4)
        (9, 'scientific', 'Scientific equipment', 4),
        (10, 'it', 'IT equipment', 4),
        (11, 'other', 'Other equipment', 4),

        -- purchase variants (module_type_id = 5)
        (12, 'consumable', 'Consumables', 5),
        (13, 'durable', 'Durable goods', 5),
        (14, 'good', 'General goods', 5),

        -- internal-services variants (module_type_id = 6)
        (15, 'it-support', 'IT support services', 6),
        (16, 'maintenance', 'Maintenance services', 6),
        (17, 'other', 'Other internal services', 6),

        -- external-cloud variants (module_type_id = 7)
        (18, 'saas', 'Software as a Service', 7),
        (19, 'iaas', 'Infrastructure as a Service', 7),
        (20, 'paas', 'Platform as a Service', 7),
        (21, 'other', 'Other cloud services', 7)
        ON CONFLICT (id) DO NOTHING;
    """)

    # Reset sequences to avoid conflicts with future inserts
    op.execute(
        "SELECT setval('module_types_id_seq', "
        "(SELECT COALESCE(MAX(id), 0) FROM module_types));"
    )
    op.execute(
        "SELECT setval('variant_types_id_seq', "
        "(SELECT COALESCE(MAX(id), 0) FROM variant_types));"
    )


def downgrade() -> None:
    """Remove seeded reference data (only if no FK references exist)."""
    # Delete variant_types first (depends on module_types)
    op.execute("""
        DELETE FROM variant_types
        WHERE id BETWEEN 1 AND 21
        AND NOT EXISTS (
            SELECT 1 FROM modules WHERE variant_type_id = variant_types.id
        );
    """)

    # Delete module_types (only if no references)
    op.execute("""
        DELETE FROM module_types
        WHERE id BETWEEN 1 AND 7
        AND NOT EXISTS (
            SELECT 1 FROM inventory_module WHERE module_type_id = module_types.id
        )
        AND NOT EXISTS (
            SELECT 1 FROM modules WHERE module_type_id = module_types.id
        );
    """)
