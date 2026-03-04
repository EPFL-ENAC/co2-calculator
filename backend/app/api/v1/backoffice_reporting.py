from typing import Annotated, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import aliased
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger

# from app.core.security import require_permission
from app.core.security import require_permission
from app.models.unit import Unit
from app.models.user import User

# Services
logger = get_logger(__name__)
router = APIRouter()


# @router.get("/units/tree")
# async def get_units_tree(
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Returns units grouped by level for cascading q-select filters.
#     Level 2 nodes contain their level-3 children, which carry
# has_children for level 4.
#     EPFL root (level 1) is implicit — not returned as a selectable filter.
#     """
#     statement = (
#         select(Unit)
#         .where(col(Unit.is_active), Unit.level >= 2)
#         .order_by(Unit.level, Unit.name)
#     )
#     units = (await db.exec(statement)).all()

#     # Index by id for O(1) parent lookup
#     by_id = {str(u.institutional_code): u for u in units}
#     tree = {}  # level-2 id -> node

#     for u in units:
#         parent_id = str(u.parent_institutional_code)
#         id_lvl = str(u.institutional_code)
#         new_node = {
#             "id": id_lvl,
#             "name": u.name,
#             "label_fr": u.label_fr,
#             "label_en": u.label_en,
#             "children": {},
#         }
#         if u.level == 2:
#             tree[id_lvl] = new_node
#         elif u.level == 3 and parent_id in by_id:
#             new_node["has_children"] = False  # updated in next level
#             tree[parent_id]["children"][id_lvl] = new_node
#         elif u.level == 4:
#             # Walk up to find level-2 ancestor via path
#             lvl3 = by_id.get(parent_id)  # get level 2 unit
#             if lvl3 and lvl3.level == 3:
#                 lvl3_id = parent_id
#                 lvl2_id = str(lvl3.parent_institutional_code)
#                 lvl3_ref = tree.get(lvl2_id, {}).get("children", {}).get(lvl3_id)
#                 if lvl3_ref is not None:
#                     new_node["has_children"] = False  # level 4 nodes are leaves
#                     new_node["unit_type_label"] = u.unit_type_label
#                     lvl3_ref["children"][id_lvl] = new_node

#     return list(tree.values())


# @router.get("/units/children/{parent_id}")
# async def get_children(
#     parent_id: str,
#     db: AsyncSession = Depends(get_db),
# ):

#     statement = (
#         select(Unit)
#         .where(Unit.parent_institutional_code == parent_id, col(Unit.is_active))
#         .order_by(Unit.name)
#     )
#     units = (await db.exec(statement)).all()
#     return units


# @router.get("/units/{unit_id}/descendants")
# async def get_descendants(
#     unit_id: int,
#     db: AsyncSession = Depends(get_db),
# ):
#     unit = db.get(Unit, unit_id)
#     if not unit:
#         raise HTTPException(404)

#     # path of target unit, e.g. "1028 12000"
#     # descendants have paths starting with "{unit.pathcf} {unit.institutional_code}"
#     subtree_prefix = f"{unit.path} {unit.institutional_code}".strip()

#     descendants = db.exec(
#         select(Unit).where(
#             col(Unit.is_active),
#             Unit.path.like(f"{subtree_prefix}%"),  # type: ignore
#         )
#     ).all()
#     return descendants


# @router.get("/units-by-level")
# async def list_units_by_level(
#     level: int | None = None,
#     parent_id: str | None = None,
#     unit_type_label: str | None = None,
#     db: AsyncSession = Depends(get_db),
# ):
#     q = select(Unit).where(col(Unit.is_active))
#     if level:
#         q = q.where(Unit.level == level)
#     if parent_id:
#         q = q.where(Unit.parent_institutional_code == parent_id)
#     if unit_type_label:
#         q = q.where(Unit.unit_type_label == unit_type_label)

#     q.order_by(Unit.name)
#     return (await db.exec(q)).all()


# @router.get("/units")
# async def list_units(
#     level: int | None = None,
#     parent_id: str | None = None,
#     unit_type_label: Optional[List[str]] = Query(None),
#     parent_unit_type_label: Optional[str] = None,
#     db: AsyncSession = Depends(get_db),
# ):
#     q = select(Unit).where(col(Unit.is_active) == True)

#     # Filter by level
#     if level is not None:
#         q = q.where(Unit.level == level)

#     # Filter by parent id
#     if parent_id:
#         q = q.where(Unit.parent_institutional_code == parent_id)

#     # ✅ Multiple unit_type_label values
#     if unit_type_label:
#         q = q.where(Unit.unit_type_label.in_(unit_type_label))

#     # ✅ Filter by parent unit type label
#     if parent_unit_type_label:
#         parent_alias = aliased(Unit)

#         q = q.join(
#             parent_alias,
#             Unit.parent_institutional_code == parent_alias.institutional_code,
#         ).where(parent_alias.unit_type_label == parent_unit_type_label)

#     # ❗ order_by must be reassigned
#     q = q.order_by(Unit.name)

#     result = await db.exec(q)
#     return result.all()


@router.get("/units", response_model=List[Unit])
async def list_units(
    level: int | None = None,
    parent_id: str | None = None,
    unit_type_labels: Annotated[list[str] | None, Query()] = None,
    parent_unit_type_label: str | None = None,
    page: int = 1,
    page_size: Annotated[int, Query(le=100)] = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "view")),
):
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

    # 3. Self-Join for Parent Filtering
    if parent_unit_type_label:
        parent_alias = aliased(Unit)
        query = query.join(
            parent_alias,
            col(Unit.parent_institutional_code) == parent_alias.institutional_code,
        ).where(parent_alias.unit_type_label == parent_unit_type_label)

    # 4. Sorting and Pagination
    offset = (page - 1) * page_size
    query = query.order_by(Unit.name).offset(offset).limit(page_size)

    # 5. Execution (The SQLModel way)
    result = await db.exec(query)
    return result.all()
