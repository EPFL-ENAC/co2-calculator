"""Every seeded data entry must be able to carry an emission.

A data entry type with no candidate emission type seeds entries that recompute
to a zero bucket total, so the module's charts come up empty in dev with no
error anywhere. This pins the mapping against drift in either the taxonomy or
``MODULE_TYPE_TO_DATA_ENTRY_TYPES``.
"""

import pytest

from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.modules.emissions.registry import MODULE_STAT_BUCKETS
from app.seed.random_generator.seed_data_entries import seed_emission_candidates

_ALL_DATA_ENTRY_TYPES = [
    (module_type, data_entry_type)
    for module_type, data_entry_types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items()
    for data_entry_type in data_entry_types
    # Planner kinds (Simulator Plan) are never randomly seeded — mirror the
    # generator's pick filter.
    if not data_entry_type.is_planner_kind
]


@pytest.mark.parametrize(
    ("module_type", "data_entry_type"),
    _ALL_DATA_ENTRY_TYPES,
    ids=[f"{ModuleTypeEnum(m).name}-{d.name}" for m, d in _ALL_DATA_ENTRY_TYPES],
)
def test_every_data_entry_type_can_seed_an_emission(module_type, data_entry_type):
    assert seed_emission_candidates(data_entry_type), (
        f"{data_entry_type.name} has no seedable emission type; entries of this "
        f"type would seed with zero emissions and "
        f"{ModuleTypeEnum(module_type).name} would recompute to an empty chart"
    )


@pytest.mark.parametrize(
    ("module_type", "data_entry_type"),
    _ALL_DATA_ENTRY_TYPES,
    ids=[f"{ModuleTypeEnum(m).name}-{d.name}" for m, d in _ALL_DATA_ENTRY_TYPES],
)
def test_seeded_emissions_land_in_their_module_buckets(module_type, data_entry_type):
    """An emission outside the module's buckets is silently dropped by recompute."""
    bucket_node_ids = {
        node.value
        for bucket_nodes in MODULE_STAT_BUCKETS[ModuleTypeEnum(module_type)]
        for node in bucket_nodes.nodes
    }
    outside = [
        emission_type.name
        for emission_type in seed_emission_candidates(data_entry_type)
        if emission_type.value not in bucket_node_ids
    ]
    assert not outside, (
        f"{data_entry_type.name} may seed {outside}, which fall outside "
        f"{ModuleTypeEnum(module_type).name}'s stat buckets"
    )
