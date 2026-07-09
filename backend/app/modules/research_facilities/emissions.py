"""Emission resolution for research facilities."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="research_facilities", scope=3, roots=(EmissionType.research_facilities,)
    ),
)

_IT_RESEARCH_FACILITY_NAMES: frozenset[str] = frozenset({"scitas", "rcp"})


def resolve_research_facilities(data: dict) -> list[EmissionType]:
    name = (data.get("researchfacility_name") or "").strip().lower()
    if name in _IT_RESEARCH_FACILITY_NAMES:
        return [EmissionType.research_facilities__it_facilities]
    return [EmissionType.research_facilities__facilities]


def resolve_animal_facilities(data: dict) -> list[EmissionType]:
    facility_type = (data.get("researchfacility_type") or "").strip().lower()
    if facility_type == "mice":
        return [EmissionType.research_facilities__animal__mice]
    if facility_type == "fish":
        return [EmissionType.research_facilities__animal__fish]
    return [EmissionType.research_facilities__animal]
