"""Unit tree levels with a meaning in the app (#500).

The unit tree depth depends on the institution. At EPFL level 4 is the lab
that owns a workspace, and levels 2 and 3 are the schools and institutes that
the back office reports on. UNIT_WORKSPACE_LEVEL and UNIT_AFFILIATION_LEVELS
set them; the lifespan calls both helpers, so a missing value stops the
startup.
"""

from app.core.config import get_settings


def workspace_level() -> int:
    """Level of the units that have a workspace (their own carbon report)."""
    level = get_settings().UNIT_WORKSPACE_LEVEL
    if level is None:
        raise ValueError("UNIT_WORKSPACE_LEVEL is not set")
    return level


def affiliation_levels() -> list[int]:
    """Levels that the back office offers as affiliations."""
    raw = get_settings().UNIT_AFFILIATION_LEVELS
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise ValueError("UNIT_AFFILIATION_LEVELS is not set")
    if not all(part.isdigit() for part in parts):
        raise ValueError(f"UNIT_AFFILIATION_LEVELS must list whole numbers: {raw!r}")
    return [int(part) for part in parts]
