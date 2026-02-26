"""Unit repository for database operations."""

from math import ceil
from typing import Any, List, Optional, Union

from attr import dataclass
from sqlalchemy import asc, desc
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport
from app.models.unit import Unit
from app.models.user import UserProvider


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

    async def get_by_code(self, provider_code: str | None) -> Optional[Unit]:
        """Get unit by code (string identifier)."""
        if provider_code is None:
            return None
        result = await self.session.exec(
            select(Unit).where(col(Unit.institutional_code) == provider_code)
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
        # Try as code (string)
        return await self.get_by_code(identifier)

    async def get_by_ids(self, unit_ids: List[int]) -> List[Unit]:
        """Get multiple units by IDs (integers)."""
        result = await self.session.exec(select(Unit).where(col(Unit.id).in_(unit_ids)))
        return list(result.all())

    async def get_by_codes(self, codes: List[str]) -> List[Unit]:
        """Get multiple units by codes (strings)."""
        result = await self.session.exec(
            select(Unit).where(col(Unit.institutional_code).in_(codes))
        )
        return list(result.all())

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        unit_id_filter: Optional[List[int]] = None,
        provider_code_filter: Optional[List[str]] = None,
    ) -> List[Unit]:
        """List units with optional filters."""
        query = select(Unit)

        if unit_id_filter:
            query = query.where(col(Unit.id).in_(unit_id_filter))
        if provider_code_filter:
            query = query.where(col(Unit.institutional_code).in_(provider_code_filter))

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
        institutional_code: str,
        name: str,
        principal_user_institutional_id: Optional[str] = None,
        path_name: Optional[str] = None,
        provider: Optional[UserProvider] = None,
        institutional_id: Optional[str] = None,
    ) -> Unit:
        """Create a new unit."""
        entity = Unit(
            institutional_code=institutional_code,
            name=name,
            principal_user_institutional_id=principal_user_institutional_id,
            path_name=path_name,
            provider=provider,
            institutional_id=institutional_id,
        )
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def bulk_create(self, units: List[Unit]) -> List[Unit]:
        """Bulk create units."""
        # db_objs = [Unit.model_validate(unit) for unit in units]
        self.session.add_all(units)
        await self.session.flush()
        return units

    async def bulk_upsert(self, units: List[Unit]) -> UpsertResult:
        if not units:
            return UpsertResult(created=0, updated=0, total=0, data=[])
        rows = (await self.session.exec(select(Unit.institutional_code, Unit.id))).all()
        existing: dict[str, int] = {code: uid for code, uid in rows if uid is not None}

        created = len(units) - len(existing)
        updated = len(existing)
        merged = []
        for unit in units:
            unit.id = existing.get(unit.institutional_code)
            result = await self.session.merge(unit)
            merged.append(result)
        return UpsertResult(
            created=created, updated=updated, total=len(units), data=merged
        )

    async def update(
        self,
        id: int,
        name: Optional[str] = None,
        principal_user_institutional_id: Optional[str] = None,
        path_name: Optional[str] = None,
        provider: Optional[UserProvider] = None,
        institutional_id: Optional[str] = None,
        institutional_code: Optional[str] = None,
    ) -> Unit:
        """Update an existing unit."""
        result = await self.session.exec(select(Unit).where(Unit.id == id))
        entity = result.one_or_none()
        if not entity:
            raise ValueError("Unit not found")

        if name is not None:
            entity.name = name
        if principal_user_institutional_id is not None:
            entity.principal_user_institutional_id = principal_user_institutional_id
        if path_name is not None:
            entity.path_name = path_name

        entity.provider = provider or entity.provider
        if institutional_id is not None:
            entity.institutional_id = institutional_id
        if institutional_code is not None:
            entity.institutional_code = institutional_code
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def upsert(
        self,
        unit_data: Unit,
    ) -> Unit:
        """Create or update a unit by code."""
        # Look up by code for upsert operations
        existing = await self.get_by_code(unit_data.institutional_code)

        # so provider is wrong
        # And cost_centers are not updated
        if existing and existing.id:
            return await self.update(
                id=existing.id,
                name=unit_data.name,
                principal_user_institutional_id=unit_data.principal_user_institutional_id,
                path_name=unit_data.path_name,
                provider=unit_data.provider,
                institutional_id=unit_data.institutional_id,
            )
        else:
            if not unit_data.institutional_code:
                raise ValueError("Unit institutional code is required")

            return await self.create(
                institutional_code=unit_data.institutional_code,
                name=unit_data.name,
                principal_user_institutional_id=unit_data.principal_user_institutional_id,
                path_name=unit_data.path_name,
                institutional_id=unit_data.institutional_id,
                provider=unit_data.provider,
            )

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count units with optional filters."""
        query = select(func.count()).select_from(Unit)

        if filters:
            for key, value in filters.items():
                if hasattr(Unit, key):
                    query = query.where(getattr(Unit, key) == value)

        result = await self.session.execute(query)
        return result.scalar_one()
