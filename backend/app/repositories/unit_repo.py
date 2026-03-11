"""Unit repository for database operations."""

from math import ceil
from typing import Any, List, Optional, Union

from attr import dataclass
from sqlalchemy import asc, desc
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport
from app.models.unit import Unit
from app.schemas.unit import UnitUpdate


@dataclass
class UpsertResult:
    created: int
    updated: int
    total: int
    data: List[Unit]

    def __str__(self) -> str:
        return (
            f"{self.total} processed ({self.created} created, {self.updated} updated)"
        )


class UnitRepository:
    """Repository for Unit database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, unit_id: int | None) -> Optional[Unit]:
        """Get unit by ID (integer)."""
        if unit_id is None:
            return None
        result = await self.session.exec(select(Unit).where(Unit.id == unit_id))
        return result.one_or_none()

    async def get_by_institutional_id(
        self, institutional_id: str | None
    ) -> Optional[Unit]:
        """Get unit by institutional_id."""
        if institutional_id is None:
            return None
        result = await self.session.exec(
            select(Unit).where(col(Unit.institutional_id) == institutional_id)
        )
        return result.one_or_none()

    async def get_by_id_or_code(
        self, identifier: Union[int, str, None]
    ) -> Optional[Unit]:
        """Get unit by either integer ID or string code."""
        if identifier is None:
            return None
        if isinstance(identifier, int):
            return await self.get_by_id(identifier)
        # Try as institutional_id (string)
        return await self.get_by_institutional_id(identifier)

    async def get_by_ids(self, unit_ids: List[int]) -> List[Unit]:
        """Get multiple units by IDs (integers)."""
        result = await self.session.exec(select(Unit).where(col(Unit.id).in_(unit_ids)))
        return list(result.all())

    async def get_by_institutional_ids(
        self, institutional_ids: List[str]
    ) -> List[Unit]:
        """Get multiple units by institutional_ids."""
        result = await self.session.exec(
            select(Unit).where(col(Unit.institutional_id).in_(institutional_ids))
        )
        return list(result.all())

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        unit_id_filter: Optional[List[int]] = None,
        institutional_id_filter: Optional[List[str]] = None,
    ) -> List[Unit]:
        """List units with optional filters."""
        query = select(Unit)

        if unit_id_filter:
            query = query.where(col(Unit.id).in_(unit_id_filter))
        if institutional_id_filter:
            query = query.where(col(Unit.institutional_id).in_(institutional_id_filter))

        query = query.offset(skip).limit(limit)
        result = await self.session.exec(query)
        return list(result.all())

    # // WIP, maybe deadcode
    async def get_units_with_filters(
        self,
        years: Optional[List[int]] = None,
        path_name: Optional[str] = None,
        name: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "name",
        descending: bool = False,
    ):

        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        # ---- Step 1: Get distinct unit IDs ----
        id_stmt = select(Unit.id)

        if years:
            id_stmt = id_stmt.join(
                CarbonReport,
                col(CarbonReport.unit_id) == col(Unit.id),
            ).where(col(CarbonReport.year).in_(years))

        if path_name:
            id_stmt = id_stmt.where(col(Unit.path_name) == path_name)

        # 🔎 Name filter (case-insensitive)
        if name:
            id_stmt = id_stmt.where(col(Unit.name).ilike(f"%{name}%"))

        id_stmt = id_stmt.distinct()

        # ---- Count ----
        count_stmt = select(func.count()).select_from(id_stmt.subquery())
        total = (await self.session.exec(count_stmt)).one()

        # ---- Step 2: Fetch full Units using IDs ----
        offset = (page - 1) * page_size

        units_stmt = select(Unit).where(col(Unit.id).in_(id_stmt))

        # Sorting
        ALLOWED_SORT_FIELDS = {
            "name": col(Unit.name),
            "id": col(Unit.id),
        }

        column = ALLOWED_SORT_FIELDS.get(sort_by, col(Unit.name))
        order_clause: Any = desc(column) if descending else asc(column)

        units_stmt = units_stmt.order_by(order_clause).offset(offset).limit(page_size)

        rows = (await self.session.exec(units_stmt)).all()

        total_pages = ceil(total / page_size) if total else 1

        return {
            "data": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    async def create(
        self,
        data: Unit,
    ) -> Unit:
        """Create a new unit."""
        db_obj = Unit.model_validate({**data.model_dump()})
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def bulk_create(self, units: List[Unit]) -> List[Unit]:
        """Bulk create units."""
        # db_objs = [Unit.model_validate(unit) for unit in units]
        self.session.add_all(units)
        await self.session.flush()
        return units

    async def bulk_upsert(self, units: List[Unit]) -> UpsertResult:
        if not units:
            return UpsertResult(created=0, updated=0, total=0, data=[])
        rows = (await self.session.exec(select(Unit.institutional_id, Unit.id))).all()
        existing: dict[str | None, int] = {
            iid: uid for iid, uid in rows if uid is not None
        }

        created = len(units) - len(existing)
        updated = len(existing)
        merged = []
        for unit in units:
            unit.id = existing.get(unit.institutional_id)
            result = await self.session.merge(unit)
            merged.append(result)
        return UpsertResult(
            created=created, updated=updated, total=len(units), data=merged
        )

    async def update(self, data: UnitUpdate) -> Optional[Unit]:
        """Update an existing unit."""
        statement = await self.session.exec(select(Unit).where(col(Unit.id) == data.id))
        db_obj = statement.one_or_none()

        if not db_obj:
            return None

        # 2. Update fields from input model (only provided fields)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        # 4. Save
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def upsert(
        self,
        unit_data: Unit,
    ) -> Unit:
        """Create or update a unit by code."""
        # Look up by institutional_id for upsert operations
        existing = await self.get_by_institutional_id(unit_data.institutional_id)

        # so provider is wrong
        # And cost_centers are not updated
        if existing and existing.id:
            update_payload = UnitUpdate(
                id=existing.id,
                name=unit_data.name,
                principal_user_institutional_id=unit_data.principal_user_institutional_id,
            )
            updated_value = await self.update(update_payload)
            if updated_value is None:
                raise ValueError("Failed to update existing unit")
            return updated_value
        else:
            if not unit_data.institutional_code:
                raise ValueError("Unit institutional code is required")

            return await self.create(unit_data)

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count units with optional filters."""
        query = select(func.count()).select_from(Unit)

        if filters:
            for key, value in filters.items():
                if hasattr(Unit, key):
                    query = query.where(getattr(Unit, key) == value)

        result = await self.session.execute(query)
        return result.scalar_one()
