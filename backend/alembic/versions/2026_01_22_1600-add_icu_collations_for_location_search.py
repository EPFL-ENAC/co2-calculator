"""add icu collations for location search

Revision ID: add_icu_collations
Revises: 8b18929d56c9
Create Date: 2026-01-22 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_icu_collations"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "8b18929d56c9"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Create ICU collations for accent-insensitive, case-insensitive search
    # These collations use Unicode level 1 (base characters only,
    # ignoring accents and case)
    op.execute(
        """
        CREATE COLLATION IF NOT EXISTS ch_fr_ci_ai (
            provider = icu,
            locale = 'fr-CH-u-ks-level1',
            deterministic = false
        )
        """
    )

    op.execute(
        """
        CREATE COLLATION IF NOT EXISTS ch_de_ci_ai (
            provider = icu,
            locale = 'de-CH-u-ks-level1',
            deterministic = false
        )
        """
    )

    op.execute(
        """
        CREATE COLLATION IF NOT EXISTS ch_it_ci_ai (
            provider = icu,
            locale = 'it-CH-u-ks-level1',
            deterministic = false
        )
        """
    )

    # Create indexes using these collations for efficient accent-insensitive search
    # We'll use ch_de_ci_ai as the primary collation (most common in Switzerland)
    # but queries can use any of the three collations
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_name_fr 
        ON locations (name COLLATE ch_fr_ci_ai)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_name_de 
        ON locations (name COLLATE ch_de_ci_ai)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_name_it 
        ON locations (name COLLATE ch_it_ci_ai)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_municipality_fr 
        ON locations (municipality COLLATE ch_fr_ci_ai)
        WHERE municipality IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_municipality_de 
        ON locations (municipality COLLATE ch_de_ci_ai)
        WHERE municipality IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_municipality_it 
        ON locations (municipality COLLATE ch_it_ci_ai)
        WHERE municipality IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_keywords_fr 
        ON locations (keywords COLLATE ch_fr_ci_ai)
        WHERE keywords IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_keywords_de 
        ON locations (keywords COLLATE ch_de_ci_ai)
        WHERE keywords IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_locations_keywords_it 
        ON locations (keywords COLLATE ch_it_ci_ai)
        WHERE keywords IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_locations_keywords_it")
    op.execute("DROP INDEX IF EXISTS idx_locations_keywords_de")
    op.execute("DROP INDEX IF EXISTS idx_locations_keywords_fr")
    op.execute("DROP INDEX IF EXISTS idx_locations_municipality_it")
    op.execute("DROP INDEX IF EXISTS idx_locations_municipality_de")
    op.execute("DROP INDEX IF EXISTS idx_locations_municipality_fr")
    op.execute("DROP INDEX IF EXISTS idx_locations_name_it")
    op.execute("DROP INDEX IF EXISTS idx_locations_name_de")
    op.execute("DROP INDEX IF EXISTS idx_locations_name_fr")

    # Drop collations
    op.execute("DROP COLLATION IF EXISTS ch_it_ci_ai")
    op.execute("DROP COLLATION IF EXISTS ch_de_ci_ai")
    op.execute("DROP COLLATION IF EXISTS ch_fr_ci_ai")
