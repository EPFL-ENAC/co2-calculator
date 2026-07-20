"""Emission resolution for professional travel."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="professional_travel", scope=3, roots=(EmissionType.professional_travel,)
    ),
)

_PLANE_CABIN_MAP: dict[str, EmissionType] = {
    "business": EmissionType.professional_travel__plane__business,
    "economy": EmissionType.professional_travel__plane__eco,
}

_TRAIN_CLASS_MAP: dict[str, EmissionType] = {
    "first": EmissionType.professional_travel__train__class_1,
    "second": EmissionType.professional_travel__train__class_2,
}


def resolve_plane(data: dict) -> list[EmissionType] | None:
    cabin = (data.get("cabin_class") or "").lower()
    emission_type = _PLANE_CABIN_MAP.get(cabin)
    return [emission_type] if emission_type else None


def resolve_train(data: dict) -> list[EmissionType] | None:
    cabin = (data.get("cabin_class") or "").lower()
    emission_type = _TRAIN_CLASS_MAP.get(cabin)
    return [emission_type] if emission_type else None
