"""remove country and factor_type from train_impact_factors

Revision ID: bbc28e5f3765
Revises: f7g8h9i0j1k2
Create Date: 2026-01-16 15:00:00.000000

"""

from typing import Sequence, Union

from sqlalchemy import inspect, text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bbc28e5f3765"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "f7g8h9i0j1k2"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Check if table exists
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "train_impact_factors" not in existing_tables:
        # Table doesn't exist, nothing to do
        return

    # Use raw SQL with IF EXISTS to safely drop indexes and columns
    # This avoids transaction errors if they don't exist

    # Drop factor_type index if it exists
    op.execute(text("DROP INDEX IF EXISTS ix_train_impact_factors_factor_type"))

    # Drop factor_type column if it exists
    op.execute(
        text("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'train_impact_factors' 
                AND column_name = 'factor_type'
            ) THEN
                ALTER TABLE train_impact_factors DROP COLUMN factor_type;
            END IF;
        END $$;
        """)
    )

    # Drop any indexes on country column (that don't include countrycode)
    op.execute(
        text("""
        DO $$ 
        DECLARE
            idx_name text;
        BEGIN
            FOR idx_name IN 
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'train_impact_factors' 
                AND indexname LIKE '%country%'
                AND indexname NOT LIKE '%countrycode%'
            LOOP
                EXECUTE 'DROP INDEX IF EXISTS ' || idx_name;
            END LOOP;
        END $$;
        """)
    )

    # Drop country column if it exists
    op.execute(
        text("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'train_impact_factors' 
                AND column_name = 'country'
            ) THEN
                ALTER TABLE train_impact_factors DROP COLUMN country;
            END IF;
        END $$;
        """)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add columns if needed (not implemented as they should not be restored)
    pass
