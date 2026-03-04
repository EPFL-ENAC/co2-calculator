from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.models.data_entry import DataEntryTypeEnum
from app.services.factor_service import FactorService

# from app.schemas.factor import FactorRead

router = APIRouter()


"""Would be a great idea to return directly
 with value being the 'id ' from the power factor table
 Example response for submodule = scientific equipment
 [ { "label": "30 to 37°C incubators", "value": "30 to 37°C incubators" }
 """


@router.get(
    "/{data_entry_type}/class-subclass-map",
    response_model=dict[str, list[str]],
)
async def get_class_subclass_map(
    data_entry_type: DataEntryTypeEnum,
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    """Get mapping of equipment classes to subclasses for a given submodule."""
    response = await FactorService(db).get_class_subclass_map(
        data_entry_type=data_entry_type
    )
    return response


# example of call
#
# http://localhost:9000/api/v1/factors/scientific/classes/Milling%20machine/power
# http://localhost:9000/api/v1/factors/scientific/classes/Agitator%20%2F%20Incubator/power?sub_class=Simple%20agitators%2Fincubators
@router.get(
    "/{data_entry_type_id}/classes/{kind:path}/power",
    response_model=Optional[dict[str, float]],
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
