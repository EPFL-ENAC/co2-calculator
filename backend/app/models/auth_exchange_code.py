"""Single-use OAuth-callback -> cookie-exchange code.

The OAuth callback writes a row here instead of setting cookies directly.
The SPA's POST /session/exchange consumes the row and receives cookies on
a same-origin response -- sidesteps Safari ITP, which can drop Set-Cookie
on the tail of a cross-site redirect chain.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _naive_utcnow() -> datetime:
    """Naive-UTC clock matching the ``DateTime()`` (no tz) column shape.

    All three datetime columns in this table are stored naive; using the
    naive-UTC factory keeps pre-insert object shape aligned with the
    post-insert reload and with the comparisons in
    :func:`app.api.v1.auth._consume_exchange_code`.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthExchangeCode(SQLModel, table=True):
    __tablename__ = "auth_exchange_code"

    code: str = Field(primary_key=True, max_length=64)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=_naive_utcnow)
    expires_at: datetime
    consumed_at: Optional[datetime] = Field(default=None)
