from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.models.data_entry import DataEntryTypeEnum
from app.services.factor_service import FactorService

# from app.schemas.factor import FactorRead

router = APIRouter()


# to be reimplemented later

# @router.get("/{submodule}/classes", response_model=list[str])


# @router.get(
#     "/{submodule}/classes/{equipment_class:path}/subclasses",
#     response_model=list[str],
# )


@router.get(
    "/{data_entry_type}/class-subclass-map",
    response_model=dict[str, list[str]],
)
async def get_class_subclass_map(
    data_entry_type: DataEntryTypeEnum,
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    """Get mapping of equipment classes to subclasses for a given submodule."""
    print("DATA ENTRY TYPE:", data_entry_type)
    response = await FactorService(db).get_class_subclass_map(
        data_entry_type=data_entry_type
    )
    return response


@router.get(
    "/{data_entry_type_id}/classes/{equipment_class:path}/power",
    response_model=dict[str, float],
)
async def get_factor(
    data_entry_type_id: DataEntryTypeEnum,
    equipment_class: str,
    db: AsyncSession = Depends(get_db),
):
    """Get factor for a given equipment class in a submodule."""
    # Implementation to be added later not sure how to implement
    return None
