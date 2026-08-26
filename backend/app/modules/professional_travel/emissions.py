"""Emission resolution for professional travel."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import (
    EmissionType,
    EmissionTypeResolutionError,
)

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="professional_travel", scope=3, roots=(EmissionType.professional_travel,)
    ),
)

# Public: also the source of truth for the frontend's cabin-class options
# (see `make gen-module-constants`) — keys are the valid `cabin_class` values.
PLANE_CABIN_MAP: dict[str, EmissionType] = {
    "business": EmissionType.professional_travel__plane__business,
    "economy": EmissionType.professional_travel__plane__eco,
}

TRAIN_CLASS_MAP: dict[str, EmissionType] = {
    "first": EmissionType.professional_travel__train__class_1,
    "second": EmissionType.professional_travel__train__class_2,
}


def _resolve_cabin(
    data: dict, cabin_map: dict[str, EmissionType], mode: str
) -> list[EmissionType]:
    cabin = (data.get("cabin_class") or "").lower()
    emission_type = cabin_map.get(cabin)
    if emission_type is None:
        raise EmissionTypeResolutionError(
            f"No emission type for {mode} cabin_class {cabin!r} — "
            f"expected one of {sorted(cabin_map)}"
        )
    return [emission_type]


def resolve_plane(data: dict) -> list[EmissionType]:
    return _resolve_cabin(data, PLANE_CABIN_MAP, "plane")


def resolve_train(data: dict) -> list[EmissionType]:
    return _resolve_cabin(data, TRAIN_CLASS_MAP, "train")
