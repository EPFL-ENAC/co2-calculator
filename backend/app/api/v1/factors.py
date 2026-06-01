from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import require_permission
from app.models.data_entry import DataEntryTypeEnum
from app.models.user import User
from app.repositories.factor_repo import FactorRepository
from app.schemas.data_entry import BaseModuleHandler
from app.services.factor_service import FactorService

router = APIRouter()


class StaleFactorResponse(BaseModel):
    """Operator-facing summary of a factor not present in the latest CSV."""

    id: int
    data_entry_type_id: int
    emission_type_id: int
    year: Optional[int]
    classification: dict
    last_seen_job_id: Optional[int]


@router.get("/stale", response_model=list[StaleFactorResponse])
async def list_stale_factors(
    year: int = Query(..., description="Report year to scope the query"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> list[StaleFactorResponse]:
    """Return factors not present in the latest successful FACTORS ingest.

    Plan 310B Part 3 — operators can detect rows that exist in the DB
    but were not in the most recent CSV upload.  These rows are
    intentionally not deleted because existing data entries may still
    reference their ids in the ``DataEntry.data`` JSON payload under
    ``primary_factor_id`` (this is a JSON value, not a real FK column);
    this endpoint surfaces them so the UI can warn that linked data
    entries are using outdated factors.

    **Required Permission**: ``backoffice.data_management.view``
    """
    rows = await FactorRepository(db).list_stale_for_year(year)
    responses: list[StaleFactorResponse] = []
    for f in rows:
        # DB-loaded rows always have an id.  A NULL id here would mean
        # the row was constructed but never flushed — surface as a 500
        # rather than mask with a sentinel 0 (which would be an invalid
        # client-side identifier).
        if f.id is None:
            raise ValueError(
                "FactorRepository.list_stale_for_year returned a row "
                "with no id; this should not happen for persisted factors."
            )
        responses.append(
            StaleFactorResponse(
                id=f.id,
                data_entry_type_id=f.data_entry_type_id,
                emission_type_id=f.emission_type_id,
                year=f.year,
                classification=f.classification or {},
                last_seen_job_id=f.last_seen_job_id,
            )
        )
    return responses


@router.get(
    "/{data_entry_type}/class-subclass-map",
    response_model=dict[str, list[str]],
)
async def get_class_subclass_map(
    data_entry_type: DataEntryTypeEnum,
    year: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[str]]:
    """Get mapping of equipment classes to subclasses for a given submodule.

    Scoped to ``year`` so the options match the year-scoped factor lookup in
    ``get_factor`` — otherwise the dropdown could offer a class that has no
    factor for the selected year.
    """
    handler = BaseModuleHandler.get_by_type(data_entry_type)
    return await FactorService(db).get_class_subclass_map(
        data_entry_type=data_entry_type,
        kind_field=handler.kind_field or "",
        subkind_field=handler.subkind_field or "",
        year=year,
    )


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
