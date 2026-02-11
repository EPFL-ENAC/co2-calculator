"""Unit repository for database operations."""

from typing import List, Optional, Union

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.unit import Unit
from app.models.user import UserProvider


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
            select(Unit).where(Unit.provider_code == provider_code)
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
            select(Unit).where(col(Unit.provider_code).in_(codes))
        )
        return list(result.all())

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        visibility_filter: Optional[List[str]] = None,
        unit_id_filter: Optional[List[int]] = None,
        provider_code_filter: Optional[List[str]] = None,
    ) -> List[Unit]:
        """List units with optional filters."""
        query = select(Unit)

        if unit_id_filter:
            query = query.where(col(Unit.id).in_(unit_id_filter))
        if provider_code_filter:
            query = query.where(col(Unit.provider_code).in_(provider_code_filter))

        query = query.offset(skip).limit(limit)
        result = await self.session.exec(query)
        return list(result.all())

    async def create(
        self,
        provider_code: str,
        name: str,
        principal_user_provider_code: Optional[str] = None,
        affiliations: Optional[List[str]] = None,
        provider: Optional[UserProvider] = None,
        cost_centers: Optional[List[str]] = None,
    ) -> Unit:
        """Create a new unit."""
        entity = Unit(
            provider_code=provider_code,
            name=name,
            principal_user_provider_code=principal_user_provider_code,
            affiliations=affiliations or [],
            provider=provider,
            cost_centers=cost_centers or [],
        )
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(
        self,
        id: int,
        name: Optional[str] = None,
        principal_user_provider_code: Optional[str] = None,
        affiliations: Optional[List[str]] = None,
        provider: Optional[UserProvider] = None,
        cost_centers: Optional[List[str]] = None,
    ) -> Unit:
        """Update an existing unit."""
        result = await self.session.exec(select(Unit).where(Unit.id == id))
        entity = result.one_or_none()
        if not entity:
            raise ValueError("Unit not found")

        if name is not None:
            entity.name = name
        if principal_user_provider_code is not None:
            entity.principal_user_provider_code = principal_user_provider_code
        if affiliations is not None:
            entity.affiliations = affiliations

        entity.provider = provider or entity.provider
        if cost_centers is not None:
            entity.cost_centers = cost_centers
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def upsert(
        self,
        unit_data: Unit,
    ) -> Unit:
        """Create or update a unit by code."""
        # Look up by code for upsert operations
        existing = await self.get_by_code(unit_data.provider_code)

        # so provider is wrong
        # And cost_centers are not updated
        if existing and existing.id:
            return await self.update(
                id=existing.id,
                name=unit_data.name,
                principal_user_provider_code=unit_data.principal_user_provider_code,
                affiliations=unit_data.affiliations,
                provider=unit_data.provider,
                cost_centers=unit_data.cost_centers,
            )
        else:
            if not unit_data.provider_code:
                raise ValueError("Unit code is required")

            return await self.create(
                provider_code=unit_data.provider_code,
                name=unit_data.name,
                principal_user_provider_code=unit_data.principal_user_provider_code,
                affiliations=unit_data.affiliations,
                provider=unit_data.provider,
                cost_centers=unit_data.cost_centers,
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
