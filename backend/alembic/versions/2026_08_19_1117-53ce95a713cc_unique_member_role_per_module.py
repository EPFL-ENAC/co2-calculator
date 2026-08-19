# codeql[py/unused-global-variable]
"""unique member role per module

Revision ID: 53ce95a713cc
Revises: 09ec5dcb3688
Create Date: 2026-08-19 11:17:37.915524

#2050 J4: replaces a check-then-act SELECT in the create workflow that two
concurrent POSTs could both pass. Declared in model code
(``DataEntry.__table_args__``) so the test schema's ``create_all`` builds it
too — the integration suite does not run Alembic.

The three ``drop_index`` calls autogenerate emitted for
``uq_carbon_projects_*`` and ``uq_active_datasource_per_module`` were
false positives (autogenerate does not recognise existing partial indexes) and
have been pruned.
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
revision: str = "53ce95a713cc"  # noqa: F841
down_revision: str | Sequence[str] | None = "09ec5dcb3688"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841

_INDEX_WHERE = "data_entry_type_id = 1 AND data ->> 'user_institutional_id' IS NOT NULL"

_DUPLICATE_CHECK = sa.text(
    """
    SELECT carbon_report_module_id,
           data ->> 'user_institutional_id' AS user_institutional_id,
           data ->> 'sius_code' AS sius_code,
           count(*) AS rows
    FROM data_entries
    WHERE data_entry_type_id = 1
      AND data ->> 'user_institutional_id' IS NOT NULL
    GROUP BY 1, 2, 3
    HAVING count(*) > 1
    ORDER BY count(*) DESC
    LIMIT 20
    """
)


def upgrade() -> None:
    """Upgrade schema."""
    # Existing duplicates would make CREATE UNIQUE INDEX fail with a bare
    # Postgres error. Report them instead: which rows to keep is a data
    # decision for a maintainer, never something a migration should guess.
    duplicates = op.get_bind().execute(_DUPLICATE_CHECK).all()
    if duplicates:
        listed = "\n".join(
            f"  module={row.carbon_report_module_id} "
            f"user_institutional_id={row.user_institutional_id!r} "
            f"sius_code={row.sius_code!r} rows={row.rows}"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot create uq_member_role_per_module: duplicate member roles "
            f"already exist (showing up to 20):\n{listed}\n"
            "Resolve them, then re-run this migration."
        )

    # CONCURRENTLY: ``data_entries`` reaches ~1M rows in real environments
    # (the lead, 2026-08-19), and a plain CREATE INDEX takes an exclusive lock
    # for the whole build — every write to the table blocks behind it. The
    # trade is that it cannot run inside a transaction, hence the autocommit
    # block, and that a failed build leaves an INVALID index behind rather
    # than rolling back. The DROP below covers a retry after such a failure;
    # the duplicate check above removes the one cause we can foresee.
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX IF EXISTS uq_member_role_per_module")
        op.create_index(
            "uq_member_role_per_module",
            "data_entries",
            [
                "carbon_report_module_id",
                sa.literal_column("(data ->> 'user_institutional_id')"),
                sa.literal_column("(data ->> 'sius_code')"),
            ],
            unique=True,
            postgresql_where=sa.text(_INDEX_WHERE),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Concurrently here too: DROP INDEX also takes an exclusive lock.
    with op.get_context().autocommit_block():
        op.drop_index(
            "uq_member_role_per_module",
            table_name="data_entries",
            postgresql_where=sa.text(_INDEX_WHERE),
            postgresql_concurrently=True,
        )
