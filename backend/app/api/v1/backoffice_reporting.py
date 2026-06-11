from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import aliased
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models.unit import Unit
from app.models.user import User
from app.schemas.unit import UnitRead
from app.utils.scoping import build_scope_subtree_predicate, gate_backoffice

# Services
logger = get_logger(__name__)
router = APIRouter()


@router.get("/affiliations", response_model=List[UnitRead])
async def list_affiliations(
    unit_type_labels: Annotated[list[str] | None, Query()] = None,
    name: Optional[str] = Query(
        None, description="Filter by unit name (partial match)"
    ),
    page: int = 1,
    page_size: Annotated[int, Query(le=100)] = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List affiliation units (Level 2 and Level 3).

    Returns merged list of:
    - Level 2: Service central, Faculté
    - Level 3: Institut

    Each unit includes its unit_type_label for UI distinction.

    Affiliation-scoped backoffice users (#862) only see units within the
    subtree of their scope unit(s).
    """
    is_global, affiliations = gate_backoffice(current_user)

    # Defence-in-depth: a non-global caller with no affiliations sees nothing.
    if not is_global and not affiliations:
        return []

    # 1. Initialize query with SQLModel's select
    query = select(Unit).where(col(Unit.is_active))

    # 2. Filter by level (2 or 3 only)
    query = query.where(col(Unit.level).in_([2, 3]))

    # 3. Dynamic Filtering
    if unit_type_labels:
        query = query.where(col(Unit.unit_type_label).in_(unit_type_labels))

    if name:
        query = query.where(col(Unit.name).ilike(f"%{name}%"))

    # 4. Affiliation scoping (#459)
    if not is_global:
        query = query.where(build_scope_subtree_predicate(affiliations))

    # 5. Sorting and Pagination
    offset = (page - 1) * page_size
    query = query.order_by(Unit.name).offset(offset).limit(page_size)

    # 6. Execution
    result = await db.exec(query)
    return result.all()


@router.get("/units", response_model=List[UnitRead])
async def list_units(
    level: int | None = None,
    parent_id: str | None = None,
    unit_type_labels: Annotated[list[str] | None, Query()] = None,
    parent_unit_type_label: str | None = None,
    name: Optional[str] = Query(
        None, description="Filter by unit name (partial match)"
    ),
    page: int = 1,
    page_size: Annotated[int, Query(le=100)] = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    is_global, affiliations = gate_backoffice(current_user)

    # Defence-in-depth: a non-global caller with no affiliations sees nothing.
    if not is_global and not affiliations:
        return []

    # 1. Initialize query with SQLModel's select
    query = select(Unit).where(col(Unit.is_active))

    # 2. Dynamic Filtering
    if level is not None:
        query = query.where(Unit.level == level)

    if parent_id:
        query = query.where(Unit.parent_institutional_code == parent_id)

    if unit_type_labels:
        # col() is useful here to ensure type safety with the .in_ operator
        query = query.where(col(Unit.unit_type_label).in_(unit_type_labels))
    if name:
        query = query.where(
            col(Unit.name).ilike(f"%{name}%")
        )  # case-insensitive partial match

    # 3. Self-Join for Parent Filtering
    if parent_unit_type_label:
        parent_alias = aliased(Unit)
        query = query.join(
            parent_alias,
            col(Unit.parent_institutional_code) == parent_alias.institutional_code,
        ).where(parent_alias.unit_type_label == parent_unit_type_label)

    # 4. Affiliation scoping (#459)
    if not is_global:
        query = query.where(build_scope_subtree_predicate(affiliations))

    # 5. Sorting and Pagination
    offset = (page - 1) * page_size
    query = query.order_by(Unit.name).offset(offset).limit(page_size)

    # 6. Execution (The SQLModel way)
    result = await db.exec(query)
    return result.all()
