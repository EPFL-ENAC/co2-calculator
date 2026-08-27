"""Emission resolution for headcount factors."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import (
    EmissionType,
    EmissionTypeResolutionError,
    canonical_token,
)

# Headcount-derived emissions are informative (per-person behaviour), never
# part of the organisational total.
STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="commuting", scope=3, roots=(EmissionType.commuting,), additional=True
    ),
    StatBucket(key="food", scope=3, roots=(EmissionType.food,), additional=True),
    StatBucket(key="waste", scope=3, roots=(EmissionType.waste,), additional=True),
)

# Declared spelling variants the EPFL factor CSVs carry. An alias is an
# explicit statement that two strings name the same leaf — not a guess. The
# parenthetical here is an annotation on the collection stream, not a
# distinct kind of textile.
_SUBCLASS_ALIASES: dict[str, str] = {
    "waste__recycling__textile_opened_march_2016": "waste__recycling__textile",
}


def resolve_headcount_factor(data: dict) -> list[EmissionType]:
    """Map a headcount factor row onto exactly one declared leaf.

    #2091: the previous "most specific name that exists wins" loop walked
    *up* the tree when the specific name was missing, so a subclass the
    taxonomy had never heard of (``recycling`` / ``neon tubes``) landed
    silently on ``waste__recycling`` — an intermediate node that already
    sums its children. Exact match or raise.
    """
    category = canonical_token(data.get("headcount_category"))
    cls = canonical_token(data.get("headcount_class"))
    subclass = canonical_token(data.get("headcount_subclass"))

    if not category:
        raise EmissionTypeResolutionError(
            f"Headcount factor row has no headcount_category: {data!r}"
        )

    name = "__".join(part for part in (category, cls, subclass) if part)
    name = _SUBCLASS_ALIASES.get(name, name)
    try:
        return [EmissionType[name]]
    except KeyError:
        raise EmissionTypeResolutionError(
            f"No emission type for headcount factor "
            f"category={category!r} class={cls!r} subclass={subclass!r} "
            f"(looked for EmissionType.{name}). Either correct the CSV or "
            f"add the leaf to app/modules/emissions/taxonomy.py."
        ) from None
