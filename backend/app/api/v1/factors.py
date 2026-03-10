from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.data_entry import DataEntryTypeEnum
from app.models.user import User
from app.services.factor_service import FactorService

router = APIRouter()


@router.get(
    "/{data_entry_type}/class-subclass-map",
    response_model=dict[str, list[str]],
)
async def get_class_subclass_map(
    data_entry_type: DataEntryTypeEnum,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[str]]:
    """Get mapping of equipment classes to subclasses for a given submodule."""
    response = await FactorService(db).get_class_subclass_map(
        data_entry_type=data_entry_type
    )
    return response


# example of call
#
# http://localhost:9000/api/v1/factors/scientific/classes/Milling%20machine/values
# http://localhost:9000/api/v1/factors/scientific/classes/Agitator%20%2F%20Incubator/values?sub_class=Simple%20agitators%2Fincubators
@router.get(
    "/{data_entry_type_id}/classes/{kind:path}/values",
    response_model=Optional[dict[str, float | int | str | None]],
)
async def get_factor(
    data_entry_type_id: DataEntryTypeEnum,
    kind: str,
    subkind: str = Query(default=None, alias="sub_class"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
