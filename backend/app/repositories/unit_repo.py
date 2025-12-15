"""Unit repository for database operations."""

from datetime import datetime
from typing import List, Optional

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.unit import Unit


class UnitRepository:
    """Repository for Unit database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, unit_id: str | None) -> Optional[Unit]:
        """Get unit by ID."""
        if not unit_id:
            return None
        result = await self.session.exec(select(Unit).where(Unit.id == unit_id))
        return result.one_or_none()

    async def get_by_ids(self, unit_ids: List[str]) -> List[Unit]:
        """Get multiple units by IDs."""
        result = await self.session.exec(select(Unit).where(col(Unit.id).in_(unit_ids)))
        return list(result.all())

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        visibility_filter: Optional[List[str]] = None,
        unit_id_filter: Optional[List[str]] = None,
    ) -> List[Unit]:
        """List units with optional filters."""
        query = select(Unit)

        if unit_id_filter:
            query = query.where(col(Unit.id).in_(unit_id_filter))
        if visibility_filter:
            query = query.where(col(Unit.visibility).in_(visibility_filter))

        query = query.offset(skip).limit(limit)
        result = await self.session.exec(query)
        return list(result.all())

    async def create(
        self,
        unit_id: str,
        name: str,
        visibility: str = "private",
        principal_user_id: Optional[str] = None,
        principal_user_function: Optional[str] = None,
        affiliations: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Unit:
        """Create a new unit."""
        now = datetime.utcnow()
        entity = Unit(
            id=unit_id,
            name=name,
            visibility=visibility,
            principal_user_id=principal_user_id,
            principal_user_function=principal_user_function,
            affiliations=affiliations or [],
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
            provider=provider,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update(
        self,
        unit_id: str,
        name: Optional[str] = None,
        visibility: Optional[str] = None,
        principal_user_id: Optional[str] = None,
        principal_user_function: Optional[str] = None,
        affiliations: Optional[List[str]] = None,
        updated_by: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Unit:
        """Update an existing unit."""
        result = await self.session.exec(select(Unit).where(Unit.id == unit_id))
        entity = result.one_or_none()
        if not entity:
            raise ValueError("Unit not found")

        now = datetime.utcnow()

        if name is not None:
            entity.name = name
        if visibility is not None:
            entity.visibility = visibility
        if principal_user_id is not None:
            entity.principal_user_id = principal_user_id
        if principal_user_function is not None:
            entity.principal_user_function = principal_user_function
        if affiliations is not None:
            entity.affiliations = affiliations

        entity.provider = provider or entity.provider

        entity.updated_at = now
        if updated_by is not None:
            entity.updated_by = updated_by

        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def upsert(
        self,
        unit_data: Unit,
        user_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Unit:
        """Create or update a unit."""
        existing = await self.get_by_id(unit_data.id)

        if existing and existing.id:
            return await self.update(
                unit_id=existing.id,
                name=unit_data.name,
                visibility=unit_data.visibility,
                principal_user_id=unit_data.principal_user_id,
                principal_user_function=unit_data.principal_user_function,
                affiliations=unit_data.affiliations,
                updated_by=user_id,
                provider=provider,
            )
        else:
            if not unit_data.id:
                raise ValueError("Unit ID is required")

            return await self.create(
                unit_id=unit_data.id,
                name=unit_data.name,
                visibility=unit_data.visibility or "private",
                principal_user_id=unit_data.principal_user_id,
                principal_user_function=unit_data.principal_user_function,
                affiliations=unit_data.affiliations,
                created_by=user_id,
                provider=provider,
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
