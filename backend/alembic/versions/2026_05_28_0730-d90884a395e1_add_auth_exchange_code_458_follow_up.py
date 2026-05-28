# codeql[py/unused-global-variable]
"""add auth_exchange_code (#458 follow-up)

Backs the BFF cookie-exchange flow (ADR-018): the OAuth callback writes a
single-use code here and redirects to the SPA's /auth/complete page, which
POSTs the code to /v1/session/exchange to obtain cookies on a same-origin
response. Sidesteps Safari ITP, which can drop Set-Cookie on the tail of a
cross-site redirect chain.

Autogenerate also flagged 7 "removed indexes" + 1 spurious ``pods`` table
(uq_aggregation_active, uq_emission_recalc_active, uq_factor_identity,
uq_factor_identity_no_year, ix_locations_keywords, ix_pipelines_module_year,
ix_pipelines_status, plus a stray ``pods`` create_table). The indexes are
partial / GIN / raw-SQL declarations not visible to SQLModel metadata and
re-detected on every autogenerate; the ``pods`` table is owned by another
plan whose migration hasn't been authored. All stripped from this revision.

Revision ID: d90884a395e1
Revises: 6293d5b22dc5
Create Date: 2026-05-28 07:30:48.113459

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "d90884a395e1"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "6293d5b22dc5"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_exchange_code",
        sa.Column(
            "code",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(
        op.f("ix_auth_exchange_code_user_id"),
        "auth_exchange_code",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_auth_exchange_code_user_id"),
        table_name="auth_exchange_code",
    )
    op.drop_table("auth_exchange_code")
