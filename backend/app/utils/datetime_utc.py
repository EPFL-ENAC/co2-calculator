"""Timezone-aware datetime helpers shared across API and repository layers."""

from datetime import datetime, timezone


def as_utc(dt: datetime) -> datetime:
    """Coerce a tz-naive datetime to UTC.

    Defends against stores that return naive values for tz-aware columns:
    SQLite test DBs always do, and long-lived dev DBs created before a
    column moved to ``DateTime(timezone=True)`` still serve naive rows
    (``create_all`` doesn't ALTER existing tables). Writers in this
    codebase always produce UTC, so treating naive as UTC is exact.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
