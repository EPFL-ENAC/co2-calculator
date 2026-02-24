from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.models.data_entry import DataEntryTypeEnum
from app.services.factor_service import FactorService

router = APIRouter()


def _unit_institutional_ids(
    cost_centers: list, provider_code: Optional[str]
) -> list[str]:
    """Return Archibus unit IDs from cost centers plus provider code."""
    normalized: list[str] = []
    seen: set[str] = set()
    for item in cost_centers:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    if provider_code:
        provider = str(provider_code).strip()
        if provider and provider not in seen:
            seen.add(provider)
            normalized.append(provider)
    return normalized


@router.get(
    "/{data_entry_type}/class-subclass-map",
    response_model=dict[str, list[str]],
)
async def get_class_subclass_map(
    data_entry_type: DataEntryTypeEnum,
    unit_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    """Get mapping of classes to subclasses for a given submodule.

    For building rooms (data_entry_type=30), returns archibus building→room
    hierarchy instead of factor-based classification.
    """
    if data_entry_type == DataEntryTypeEnum.building:
        from app.repositories.archibus_room_repo import ArchibusRoomRepository
        from app.repositories.unit_repo import UnitRepository

        repo = ArchibusRoomRepository(db)
        if unit_id is None:
            return {}
        unit = await UnitRepository(db).get_by_id(unit_id)
        if unit is None:
            return {}
        unit_institutional_ids = _unit_institutional_ids(
            unit.cost_centers or [],
            unit.provider_code,
        )
        rooms = await repo.list_rooms(unit_institutional_ids=unit_institutional_ids)
        mapping: dict[str, list[str]] = {}
        for room in rooms:
            if room.building_name not in mapping:
                mapping[room.building_name] = []
            if room.room_name not in mapping[room.building_name]:
                mapping[room.building_name].append(room.room_name)
        return dict(sorted(mapping.items()))

    response = await FactorService(db).get_class_subclass_map(
        data_entry_type=data_entry_type
    )
    return response


@router.get(
    "/{data_entry_type}/classification-tree",
)
async def get_classification_tree(
    data_entry_type: DataEntryTypeEnum,
    unit_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get recursive classification tree for cascading dropdowns.

    Returns a nested dict where keys are option values at each level
    and leaves are empty dicts.
    For building rooms, returns archibus building->room hierarchy.
    For equipment, returns class->subclass hierarchy from factors.
    """
    if data_entry_type == DataEntryTypeEnum.building:
        from app.repositories.archibus_room_repo import ArchibusRoomRepository
        from app.repositories.unit_repo import UnitRepository

        repo = ArchibusRoomRepository(db)
        if unit_id is None:
            return {}
        unit = await UnitRepository(db).get_by_id(unit_id)
        if unit is None:
            return {}
        unit_institutional_ids = _unit_institutional_ids(
            unit.cost_centers or [],
            unit.provider_code,
        )
        rooms = await repo.list_rooms(unit_institutional_ids=unit_institutional_ids)
        tree: dict = {}
        for room in rooms:
            if room.building_name not in tree:
                tree[room.building_name] = {}
            if room.room_name not in tree[room.building_name]:
                tree[room.building_name][room.room_name] = {}
        return dict(sorted((k, dict(sorted(v.items()))) for k, v in tree.items()))

    return await FactorService(db).get_classification_tree(
        data_entry_type=data_entry_type
    )


@router.get(
    "/{data_entry_type}/factor-kinds",
    response_model=list[str],
)
async def get_factor_kinds(
    data_entry_type: DataEntryTypeEnum,
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Get distinct factor kind values for a given data entry type."""
    factor_map = await FactorService(db).get_class_subclass_map(
        data_entry_type=data_entry_type
    )
    return sorted(factor_map.keys())


# example of call
#
# http://localhost:9000/api/v1/factors/scientific/classes/Milling%20machine/values
# http://localhost:9000/api/v1/factors/scientific/classes/Agitator%20%2F%20Incubator/values?sub_class=Simple%20agitators%2Fincubators
@router.get(
    "/{data_entry_type_id}/classes/{kind:path}/values",
    response_model=Optional[dict[str, float | str]],
)
async def get_factor(
    data_entry_type_id: DataEntryTypeEnum,
    kind: str,
    subkind: str = Query(default=None, alias="sub_class"),
    db: AsyncSession = Depends(get_db),
):
    """Get factor for a given equipment class in a submodule."""
    if not kind:
        return None
    factor = await FactorService(db).get_by_classification(
        data_entry_type=data_entry_type_id,
        kind=kind,
        subkind=subkind,
    )
    if factor:
        return factor.values
    return None
