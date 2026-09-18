"""Shared helpers for the perf suite (#2295), importable WITHOUT locust —
importing locust outside its own gevent-patched entrypoint breaks
(SSL RecursionError on Python 3.14), so anything table_matrix.py needs
lives here and locustfile.py re-exports it.
"""

import os
from datetime import timedelta
from pathlib import Path

from app.core.security import create_access_token
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.models.user import UserProvider
from app.schemas.data_entry import MODULE_HANDLERS

TABLE_PAGE_LIMITS = (20, 100, 500, 1000)

# Computed sort columns the repo adds on top of handler.sort_map
# (data_entry_repo.py — kg_co2eq always; type-specific joins).
EXTRA_SORT_COLUMNS: dict[DataEntryTypeEnum, list[str]] = {
    DataEntryTypeEnum.building: ["room_surface_square_meter"],
    DataEntryTypeEnum.plane: ["distance_km", "origin_name", "destination_name"],
    DataEntryTypeEnum.train: ["distance_km", "origin_name", "destination_name"],
}


def sort_columns(entry_type: DataEntryTypeEnum) -> list[str]:
    """Sortable columns for a submodule — handler.sort_map keys (the same
    source the repo validates against) plus the repo's computed columns.
    """
    handler = MODULE_HANDLERS.get(entry_type)
    columns = list(handler.sort_map.keys()) if handler else ["id"]
    columns += ["kg_co2eq"] + EXTRA_SORT_COLUMNS.get(entry_type, [])
    return list(dict.fromkeys(columns))


def module_of(data_entry_type: DataEntryTypeEnum) -> ModuleTypeEnum:
    for module_type, types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items():
        if data_entry_type in types:
            return module_type
    raise ValueError(f"{data_entry_type} has no owning module type")


def slug(module_type: ModuleTypeEnum) -> str:
    return module_type.name.replace("_", "-")


def mint_auth_cookie(institutional_id: str) -> str:
    """Access token for a seeded DEFAULT-provider user, identical in shape
    to what _set_auth_cookies issues — resolution only needs the
    (institutional_id, provider) pair and a valid signature.
    """
    return create_access_token(
        data={
            "sub": institutional_id,
            "email": f"{institutional_id}@example.org",
            "institutional_id": institutional_id,
            "provider": str(int(UserProvider.DEFAULT)),
            "type": "access",
        },
        expires_delta=timedelta(hours=6),
    )


# Perf upload CSVs (make perf-csvs); shared with pipeline_connections.py.
CSV_DIR = Path(
    os.environ.get(
        "PERF_CSV_DIR", str(Path(__file__).resolve().parents[2] / "INPUT_DATA" / "perf")
    )
)

# Upload/prefill jobs poll every POLL_INTERVAL s until JOB_TIMEOUT s.
JOB_TIMEOUT = float(os.environ.get("PERF_JOB_TIMEOUT", "600"))
POLL_INTERVAL = float(os.environ.get("PERF_POLL_INTERVAL", "2"))

# IngestionState / IngestionResult are int enums in the model, but the
# pipeline endpoint serializes them by NAME.
STATE_FINISHED = "FINISHED"
RESULT_ERROR = "ERROR"

# Output names of scripts/generate_perf_test_csvs.py, keyed by ingest type.
CSV_BY_TYPE = {
    DataEntryTypeEnum.member: "perf_headcount_member.csv",
    DataEntryTypeEnum.student: "perf_headcount_student.csv",
    DataEntryTypeEnum.scientific: "perf_equipment_scientific.csv",
    DataEntryTypeEnum.it: "perf_equipment_it.csv",
    DataEntryTypeEnum.other: "perf_equipment_other.csv",
    DataEntryTypeEnum.plane: "perf_travel_planes.csv",
    DataEntryTypeEnum.train: "perf_travel_trains.csv",
    DataEntryTypeEnum.building: "perf_building_rooms.csv",
    DataEntryTypeEnum.energy_combustion: "perf_building_energycombustions.csv",
    DataEntryTypeEnum.external_clouds: "perf_external_clouds.csv",
    DataEntryTypeEnum.external_ai: "perf_external_ai.csv",
    DataEntryTypeEnum.process_emissions: "perf_processemissions.csv",
    DataEntryTypeEnum.scientific_equipment: "perf_purchases_scientific_equipment.csv",
    DataEntryTypeEnum.it_equipment: "perf_purchases_it_equipment.csv",
    DataEntryTypeEnum.consumable_accessories: (
        "perf_purchases_consumable_accessories.csv"
    ),
    DataEntryTypeEnum.biological_chemical_gaseous_product: (
        "perf_purchases_biological_chemical_gaseous_product.csv"
    ),
    DataEntryTypeEnum.services: "perf_purchases_services.csv",
    DataEntryTypeEnum.vehicles: "perf_purchases_vehicles.csv",
    DataEntryTypeEnum.other_purchases: "perf_purchases_other_purchases.csv",
    DataEntryTypeEnum.purchases_centralized: "perf_purchases_centralized.csv",
    DataEntryTypeEnum.research_facilities: "perf_researchfacilities_common.csv",
    DataEntryTypeEnum.animal_facilities: "perf_researchfacilities_animals.csv",
}
