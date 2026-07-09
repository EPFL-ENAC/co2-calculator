"""Emission type registry: resolution and stat-bucket collection.

Aggregates what each module declares in its ``emissions.py`` — runtime
emission-type resolvers and ``STAT_BUCKETS`` — into the lookup tables the
data-entry pipeline and the stats recompute consume.
"""

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.modules.buildings.emissions import (
    STAT_BUCKETS as BUILDINGS_BUCKETS,
)
from app.modules.buildings.emissions import (
    resolve_building_rooms,
    resolve_combustion,
)
from app.modules.emissions.buckets import BucketNodes, StatBucket, expand_bucket
from app.modules.emissions.taxonomy import EmissionType, FactorLike
from app.modules.equipment.emissions import STAT_BUCKETS as EQUIPMENT_BUCKETS
from app.modules.external_cloud_and_ai.emissions import (
    STAT_BUCKETS as EXTERNAL_BUCKETS,
)
from app.modules.external_cloud_and_ai.emissions import (
    resolve_ai,
    resolve_clouds,
)
from app.modules.headcount.emissions import (
    STAT_BUCKETS as HEADCOUNT_BUCKETS,
)
from app.modules.headcount.emissions import (
    resolve_headcount_factor,
)
from app.modules.process_emissions.emissions import (
    STAT_BUCKETS as PROCESS_BUCKETS,
)
from app.modules.process_emissions.emissions import (
    resolve_process_emissions,
)
from app.modules.professional_travel.emissions import (
    STAT_BUCKETS as TRAVEL_BUCKETS,
)
from app.modules.professional_travel.emissions import (
    resolve_plane,
    resolve_train,
)
from app.modules.purchase.emissions import (
    STAT_BUCKETS as PURCHASE_BUCKETS,
)
from app.modules.purchase.emissions import (
    resolve_purchases_centralized,
)
from app.modules.research_facilities.emissions import (
    STAT_BUCKETS as RESEARCH_BUCKETS,
)
from app.modules.research_facilities.emissions import (
    resolve_animal_facilities,
    resolve_research_facilities,
)

# Display order of the results charts: headcount precedes buildings so the
# additional buckets come out as commuting/food/waste then embodied_energy,
# while the non-additional sequence starts at process_emissions.
_MODULE_BUCKET_SOURCES: tuple[tuple[ModuleTypeEnum, tuple[StatBucket, ...]], ...] = (
    (ModuleTypeEnum.process_emissions, PROCESS_BUCKETS),
    (ModuleTypeEnum.headcount, HEADCOUNT_BUCKETS),
    (ModuleTypeEnum.buildings, BUILDINGS_BUCKETS),
    (ModuleTypeEnum.equipment, EQUIPMENT_BUCKETS),
    (ModuleTypeEnum.external_cloud_and_ai, EXTERNAL_BUCKETS),
    (ModuleTypeEnum.purchase, PURCHASE_BUCKETS),
    (ModuleTypeEnum.research_facilities, RESEARCH_BUCKETS),
    (ModuleTypeEnum.professional_travel, TRAVEL_BUCKETS),
)

MODULE_STAT_BUCKETS: dict[ModuleTypeEnum, tuple[BucketNodes, ...]] = {
    module_type: tuple(expand_bucket(bucket) for bucket in buckets)
    for module_type, buckets in _MODULE_BUCKET_SOURCES
}

# Non-additional buckets first (declaration order), additional buckets after —
# the persisted stats dicts inherit this insertion order.
ORDERED_STAT_BUCKETS: tuple[tuple[ModuleTypeEnum, BucketNodes], ...] = tuple(
    sorted(
        (
            (module_type, bucket_nodes)
            for module_type, all_nodes in MODULE_STAT_BUCKETS.items()
            for bucket_nodes in all_nodes
        ),
        key=lambda pair: pair[1].bucket.additional,
    )
)

_ADDITIONAL_EMISSION_TYPE_IDS: frozenset[int] = frozenset(
    node.value
    for _, bucket_nodes in ORDERED_STAT_BUCKETS
    if bucket_nodes.bucket.additional
    for node in bucket_nodes.nodes
)


def is_additional_breakdown_emission(emission_type_id: int) -> bool:
    return emission_type_id in _ADDITIONAL_EMISSION_TYPE_IDS


# GHG scope persisted on DataEntryEmission rows, derived from the bucket a
# node reports under. Rollup nodes stay None (NULL scope marks them in DB).
_EMISSION_TYPE_SCOPE: dict[int, int] = {
    node.value: bucket_nodes.bucket.scope
    for _, bucket_nodes in ORDERED_STAT_BUCKETS
    for node in bucket_nodes.data_nodes
}


def emission_type_scope(emission_type: EmissionType) -> int | None:
    return _EMISSION_TYPE_SCOPE.get(emission_type.value)


DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION: dict[DataEntryTypeEnum, EmissionType] = {
    DataEntryTypeEnum.building: EmissionType.buildings__rooms,
    DataEntryTypeEnum.member: EmissionType.headcount,
    DataEntryTypeEnum.student: EmissionType.headcount,
}

ROLLUP_EMISSION_TYPE_IDS: frozenset[int] = frozenset(
    e.value for e in DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION.values()
)

FACTOR_TO_EMISSION_TYPES: dict[DataEntryTypeEnum, EmissionType] = {
    DataEntryTypeEnum.building: EmissionType.buildings__rooms,
    DataEntryTypeEnum.plane: EmissionType.professional_travel__plane,
    DataEntryTypeEnum.train: EmissionType.professional_travel__train,
}

DATA_ENTRY_TO_EMISSION_TYPES: dict[DataEntryTypeEnum, list[EmissionType] | None] = {
    DataEntryTypeEnum.member: [
        EmissionType.food,
        EmissionType.waste,
        EmissionType.commuting,
    ],
    DataEntryTypeEnum.student: [
        EmissionType.food,
        EmissionType.waste,
        EmissionType.commuting,
    ],
    DataEntryTypeEnum.building_embodied_energy: [
        EmissionType.buildings__construction_and_renovation
    ],
    DataEntryTypeEnum.scientific: [EmissionType.equipment__scientific],
    DataEntryTypeEnum.it: [EmissionType.equipment__it],
    DataEntryTypeEnum.other: [EmissionType.equipment__other],
    DataEntryTypeEnum.scientific_equipment: [
        EmissionType.purchases__scientific_equipment
    ],
    DataEntryTypeEnum.it_equipment: [EmissionType.purchases__it_equipment],
    DataEntryTypeEnum.consumable_accessories: [
        EmissionType.purchases__consumable_accessories
    ],
    DataEntryTypeEnum.biological_chemical_gaseous_product: [
        EmissionType.purchases__biological_chemical_gaseous
    ],
    DataEntryTypeEnum.services: [EmissionType.purchases__services],
    DataEntryTypeEnum.vehicles: [EmissionType.purchases__vehicles],
    DataEntryTypeEnum.other_purchases: [EmissionType.purchases__other],
    DataEntryTypeEnum.external_ai: [
        EmissionType.external__ai__provider_google,
        EmissionType.external__ai__provider_mistral_ai,
        EmissionType.external__ai__provider_anthropic,
        EmissionType.external__ai__provider_openai,
        EmissionType.external__ai__provider_cohere,
        EmissionType.external__ai__provider_others,
    ],
}

_RUNTIME_RESOLVERS = {
    DataEntryTypeEnum.plane: resolve_plane,
    DataEntryTypeEnum.train: resolve_train,
    DataEntryTypeEnum.energy_combustion: resolve_combustion,
    DataEntryTypeEnum.purchases_centralized: resolve_purchases_centralized,
    DataEntryTypeEnum.external_ai: resolve_ai,
    DataEntryTypeEnum.external_clouds: resolve_clouds,
    DataEntryTypeEnum.process_emissions: resolve_process_emissions,
    DataEntryTypeEnum.member: resolve_headcount_factor,
    DataEntryTypeEnum.student: resolve_headcount_factor,
    DataEntryTypeEnum.research_facilities: resolve_research_facilities,
    DataEntryTypeEnum.mice_and_fish_animal_facilities: resolve_animal_facilities,
}


def resolve_factor_emission_type(
    data_entry_type: DataEntryTypeEnum,
    factor: dict,
) -> EmissionType | None:
    static = FACTOR_TO_EMISSION_TYPES.get(data_entry_type)
    if static is not None:
        return static

    resolver = _RUNTIME_RESOLVERS.get(data_entry_type)
    types = resolver(factor) if resolver else None
    if types is None:
        types = DATA_ENTRY_TO_EMISSION_TYPES.get(data_entry_type)
    if types is None or len(types) == 0:
        return None
    if len(types) > 1:
        raise ValueError(
            f"Expected exactly one emission type for factor of type {data_entry_type},"
            f" but got multiple: {types}"
            f" for row: {factor}"
        )
    return types[0]


def resolve_emission_types(
    data_entry_type: DataEntryTypeEnum,
    data: dict,
    *,
    factor: FactorLike | None = None,
) -> list[EmissionType] | None:
    static = DATA_ENTRY_TO_EMISSION_TYPES.get(data_entry_type)
    if static is not None:
        return static

    if data_entry_type is DataEntryTypeEnum.building:
        return resolve_building_rooms(data, factor)

    resolver = _RUNTIME_RESOLVERS.get(data_entry_type)
    if resolver:
        return resolver(data)

    return None
