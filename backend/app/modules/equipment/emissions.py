"""Emission stat buckets for the equipment module."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(key="equipment", scope=2, roots=(EmissionType.equipment,)),
)
