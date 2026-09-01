# codeql[py/unused-global-variable]
"""trigram index on classification translation labels

Revision ID: 956c36805397
Revises: 42aecc9a8a5b
Create Date: 2026-09-01 09:36:18.094264

"""

from collections.abc import Sequence

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "956c36805397"  # noqa: F841
down_revision: str | Sequence[str] | None = "42aecc9a8a5b"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


# Hand content, autogenerate can't express opclasses: GIN trigram index
# on the label column — the filter subqueries and the typeahead both run
# leading-wildcard ILIKE over it (#2401 review). Mirrors the
# locations.keywords precedent from the initial migration; pg_trgm is
# already installed there.


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_classification_translations_label_trgm",
        "classification_translations",
        ["label"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"label": "gin_trgm_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_classification_translations_label_trgm",
        table_name="classification_translations",
        postgresql_using="gin",
        postgresql_ops={"label": "gin_trgm_ops"},
    )
