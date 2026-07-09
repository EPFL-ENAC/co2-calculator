"""Emission resolution for headcount factors."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

# Headcount-derived emissions are informative (per-person behaviour), never
# part of the organisational total.
STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="commuting", scope=3, roots=(EmissionType.commuting,), additional=True
    ),
    StatBucket(key="food", scope=3, roots=(EmissionType.food,), additional=True),
    StatBucket(key="waste", scope=3, roots=(EmissionType.waste,), additional=True),
)


def resolve_headcount_factor(data: dict) -> list[EmissionType] | None:
    category = (data.get("headcount_category") or "").strip().lower()
    cls = (data.get("headcount_class") or "").strip().lower()
    subclass = (data.get("headcount_subclass") or "").strip().lower()

    if not category:
        return None

    # Most specific enum name that exists wins.
    names = [category]
    if cls:
        names.append(f"{category}__{cls}")
        if subclass:
            names.append(f"{category}__{cls}__{subclass}")
    for name in reversed(names):
        try:
            return [EmissionType[name]]
        except KeyError:
            continue
    return None
