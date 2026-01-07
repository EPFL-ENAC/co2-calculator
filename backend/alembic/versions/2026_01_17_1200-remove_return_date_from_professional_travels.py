"""remove return_date from professional_travels

Revision ID: 3ed22e605e2a
Revises: 1c3ba772940b
Create Date: 2026-01-17 12:00:00.000000

"""

from typing import Sequence, Union

from sqlalchemy import inspect, text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ed22e605e2a"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "1c3ba772940b"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Check if table exists
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "professional_travels" not in existing_tables:
        # Table doesn't exist, nothing to do
        return

    # Use raw SQL with IF EXISTS to safely drop the column
    # This avoids transaction errors if it doesn't exist
    op.execute(
        text("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'professional_travels' 
                AND column_name = 'return_date'
            ) THEN
                ALTER TABLE professional_travels DROP COLUMN return_date;
            END IF;
        END $$;
        """)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add return_date column if needed
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "professional_travels" not in existing_tables:
        return

    # Check if column already exists before adding
    op.execute(
        text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'professional_travels' 
                AND column_name = 'return_date'
            ) THEN
                ALTER TABLE professional_travels 
                ADD COLUMN return_date DATE;
            END IF;
        END $$;
        """)
    )
