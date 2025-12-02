"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)} # noqa: F841
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)} # noqa: F841
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)} # noqa: F841
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)} # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
