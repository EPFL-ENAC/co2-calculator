"""Factor routes.

Form options no longer come from here: ``GET taxonomies/module/{module}/
{data_entry}`` (and its batch sibling) is the single lookup endpoint since
#2391 decision 1, which retired ``/class-subclass-map`` and ``/list``. What
remains is the narrow per-class values prefill below — the only place a
client legitimately reads factor values.
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.data_entry import DataEntryTypeEnum
from app.models.user import User
from app.services.factor_service import FactorService

router = APIRouter()


# example of call
#
# http://localhost:9000/api/v1/factors/scientific/classes/Milling%20machine/values
# http://localhost:9000/api/v1/factors/scientific/classes/Agitator%20%2F%20Incubator/values?sub_class=Simple%20agitators%2Fincubators
@router.get(
    "/{data_entry_type_id}/classes/{kind:path}/values",
    response_model=dict[str, float | int | str | None] | None,
)
async def get_factor(
    data_entry_type_id: DataEntryTypeEnum,
    kind: str,
    subkind: str = Query(default=None, alias="sub_class"),
    year: int = Query(...),
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
        year=year,
    )
    if factor:
        # For combustion factors, `unit` lives in `classification` rather than `values`.
        # Merge both so callers receive a single flat dict; values win on key collision.
        # This mght be a hack with unintended consequences.
        return {**(factor.classification or {}), **(factor.values or {})}
    return None
