"""Emission resolution for research facilities."""

from app.core.config import get_settings
from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="research_facilities", scope=3, roots=(EmissionType.research_facilities,)
    ),
)


def _it_research_facility_ids() -> frozenset[str]:
    return frozenset(
        fid.strip()
        for fid in get_settings().IT_RESEARCH_FACILITY_IDS.split(",")
        if fid.strip()
    )


_ANIMAL_TYPE_EMISSIONS: dict[str, EmissionType] = {
    "rodent": EmissionType.research_facilities__animal__rodent,
    "fish": EmissionType.research_facilities__animal__fish,
}


def resolve_research_facilities(data: dict) -> list[EmissionType]:
    facility_id = (data.get("researchfacility_id") or "").strip()
    if facility_id in _it_research_facility_ids():
        return [EmissionType.research_facilities__it_facilities]
    return [EmissionType.research_facilities__facilities]


def resolve_animal_facilities(data: dict) -> list[EmissionType]:
    facility_type = (data.get("researchfacility_type") or "").strip().lower()
    emission_type = _ANIMAL_TYPE_EMISSIONS.get(facility_type)
    if emission_type is None:
        raise ValueError(
            f"Unknown animal facility type {facility_type!r} — "
            f"expected one of {sorted(_ANIMAL_TYPE_EMISSIONS)}"
        )
    return [emission_type]
