"""Generic parsing utilities for data transformation."""

from datetime import date, datetime
from typing import Any, Optional


def parse_date_str(date_str: str) -> Optional[date]:
    """Parse date from various formats including YYYYMMDD."""
    if not date_str:
        return None
    # Handle YYYYMMDD format from CSV
    if len(date_str) == 8 and date_str.isdigit():
        return datetime.strptime(date_str, "%Y%m%d").date()
    # Try ISO format
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None


def parse_bool(value: Any) -> bool:
    """Parse boolean from various formats."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.upper() in ("YES", "TRUE", "1")
    return bool(value) if value else False


def parse_float(value: Any) -> Optional[float]:
    """Safely parse float values."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_int(value: Any, default: int = 0) -> int:
    """Safely parse integer values."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
