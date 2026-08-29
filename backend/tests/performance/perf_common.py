"""Shared helpers for the perf suite (#2295), importable WITHOUT locust —
importing locust outside its own gevent-patched entrypoint breaks
(SSL RecursionError on Python 3.14), so anything table_matrix.py needs
lives here and locustfile.py re-exports it.
"""

from datetime import timedelta

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
