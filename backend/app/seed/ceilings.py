"""Real per-data_entry_type ceiling estimates (#2161).

Sourced from the requester's numbers on GitHub issue #2161 (2026-08-18) —
the only calculator-type row without a number was
``building_embodied_energy``: it maps to the (already-renamed)
``building_construction_renovation`` concept; kept under its current enum
name here since the model hasn't been renamed.

Single source of truth for the ceiling numbers. Both
``scripts/generate_perf_test_csvs.py`` and the load-test backdrop seeder
(``app/seed/random_generator/seed_data_entries.py``, ``SEED_CEILING_SCALE``
mode) read this table rather than keeping their own copy.
"""

from app.models.data_entry import DataEntryTypeEnum

CEILING_PER_UNIT_YEAR: dict[DataEntryTypeEnum, int] = {
    DataEntryTypeEnum.member: 500,
    DataEntryTypeEnum.student: 500,
    DataEntryTypeEnum.scientific: 1000,
    DataEntryTypeEnum.it: 1000,
    DataEntryTypeEnum.other: 1000,
    DataEntryTypeEnum.plane: 500,
    DataEntryTypeEnum.train: 5000,
    DataEntryTypeEnum.building: 500,
    DataEntryTypeEnum.energy_combustion: 500,
    DataEntryTypeEnum.building_embodied_energy: 500,
    DataEntryTypeEnum.external_clouds: 500,
    DataEntryTypeEnum.external_ai: 500,
    DataEntryTypeEnum.process_emissions: 500,
    DataEntryTypeEnum.scientific_equipment: 1000,
    DataEntryTypeEnum.it_equipment: 1000,
    DataEntryTypeEnum.consumable_accessories: 1000,
    DataEntryTypeEnum.biological_chemical_gaseous_product: 1000,
    DataEntryTypeEnum.services: 1000,
    DataEntryTypeEnum.vehicles: 1000,
    DataEntryTypeEnum.other_purchases: 1000,
    DataEntryTypeEnum.purchases_centralized: 1000,
    DataEntryTypeEnum.research_facilities: 500,
    DataEntryTypeEnum.animal_facilities: 50,
}

TOTAL_CEILING_PER_UNIT_YEAR = sum(CEILING_PER_UNIT_YEAR.values())
