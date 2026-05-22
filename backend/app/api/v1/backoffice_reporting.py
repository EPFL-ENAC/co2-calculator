from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models.unit import Unit
from app.models.user import User
from app.schemas.unit import UnitRead
from app.utils.permissions import derive_backoffice_affiliations, has_permission

# Services
logger = get_logger(__name__)
router = APIRouter()


def _affiliation_predicate(affiliations: set[str]) -> ColumnElement[bool]:
    """Build the SQL predicate matching ``Unit.path_name`` against affiliations.

    ACCRED ``sortpath`` is a single token (e.g. ``"SV"``, ``"STI"``,
    ``"Engineering"``); ``Unit.path_name`` is a separator-joined ancestor list
    (observed shapes: ``"EPFL > STI > LMSC"`` and ``"EPFL ENAC IT4R-TEST"``).
    Padding the column with leading/trailing spaces lets a single
    ``% <aff> %`` ILIKE catch tokens at any position regardless of separator
    (` > ` or plain space) and avoids false positives like ``SV`` matching
    ``SVOPS``.
    """
    # ``coalesce`` keeps the predicate well-defined when ``path_name`` is NULL
    # (NULL rows simply never match).
    padded = func.concat(" ", func.coalesce(col(Unit.path_name), ""), " ")
    return or_(*[padded.ilike(f"% {aff} %") for aff in affiliations])


def _gate_backoffice_users_view(user: User) -> tuple[bool, set[str]]:
    """Authorize ``backoffice.users.view`` and return the caller's scope.

    Raises 403 if the user holds neither the bare ``backoffice.users`` key nor
    any ``backoffice.users/<aff>`` key. Returns ``(is_global, affiliations)``;
    callers apply the affiliation predicate when ``is_global`` is False.

    Uses ``has_permission(..., any_scope=True)`` because affiliation-scoped
    users only hold ``backoffice.users/<aff>`` keys — ``require_permission``'s
    literal-path lookup would 403 them.
    """
    perms = user.calculate_permissions()
    if not has_permission(perms, "backoffice.users", "view", any_scope=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return derive_backoffice_affiliations(perms)


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

    Affiliation-scoped backoffice users (#459) only see units whose
    ``path_name`` contains one of their affiliations.
    """
    is_global, affiliations = _gate_backoffice_users_view(current_user)

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
        query = query.where(_affiliation_predicate(affiliations))

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
    is_global, affiliations = _gate_backoffice_users_view(current_user)

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
        query = query.where(_affiliation_predicate(affiliations))

    # 5. Sorting and Pagination
    offset = (page - 1) * page_size
    query = query.order_by(Unit.name).offset(offset).limit(page_size)

    # 6. Execution (The SQLModel way)
    result = await db.exec(query)
    return result.all()
