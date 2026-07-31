"""Emission resolution for research facilities."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="research_facilities", scope=3, roots=(EmissionType.research_facilities,)
    ),
)

_IT_RESEARCH_FACILITY_IDS: frozenset[str] = frozenset(
    {
        "0616",  # ISIC-ITDMP
        "1027",  # IMAGING-GE
        "1202",  # RCP-GE
        "1800",  # DCI-GE
        "1902",  # SCITAS-GE
        "1915",  # SCALA-GE
        "1916",  # SDSC-GE
        "2043",  # CIBM-GE
        "2044",  # CIBM-MRI
    }
)

_ANIMAL_TYPE_EMISSIONS: dict[str, EmissionType] = {
    "rodent": EmissionType.research_facilities__animal__rodent,
    "fish": EmissionType.research_facilities__animal__fish,
}


def resolve_research_facilities(data: dict) -> list[EmissionType]:
    facility_id = (data.get("researchfacility_id") or "").strip()
    if facility_id in _IT_RESEARCH_FACILITY_IDS:
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
