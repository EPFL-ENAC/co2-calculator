"""UnitUser repository for database operations.

This repository handles the many-to-many relationship between Units and Users.
"""

from typing import List, Optional

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.unit_user import UnitUser
from app.models.user import RoleName


class UnitUserRepository:
    """Repository for UnitUser database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> Optional[UnitUser]:
        """Get UnitUser association by ID."""
        result = await self.session.exec(select(UnitUser).where(UnitUser.id == id))
        return result.one_or_none()

    async def get_by_unit_and_user(
        self, unit_id: int, user_id: int
    ) -> Optional[UnitUser]:
        """Get UnitUser association by unit ID and user ID."""
        result = await self.session.exec(
            select(UnitUser).where(
                (UnitUser.user_id == user_id) & (UnitUser.unit_id == unit_id)
            )
        )
        return result.one_or_none()

    async def get_by_user(self, user_id: int) -> List[UnitUser]:
        """Get all unit associations for a specific user."""
        result = await self.session.exec(
            select(UnitUser).where(UnitUser.user_id == user_id)
        )
        return list(result.all())

    async def get_by_unit(self, unit_id: int) -> List[UnitUser]:
        """Get all user associations for a specific unit."""
        result = await self.session.exec(
            select(UnitUser).where(UnitUser.unit_id == unit_id)
        )
        return list(result.all())

    async def create(
        self,
        unit_id: int,
        user_id: int,
        role: RoleName,
    ) -> UnitUser:
        """Create a new UnitUser association."""
        entity = UnitUser(
            unit_id=unit_id,
            user_id=user_id,
            role=role.value,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update_role(
        self,
        unit_id: int,
        user_id: int,
        role: RoleName,
    ) -> UnitUser:
        """Update the role for a UnitUser association."""
        result = await self.session.exec(
            select(UnitUser).where(
                (UnitUser.user_id == user_id) & (UnitUser.unit_id == unit_id)
            )
        )
        entity = result.one_or_none()
        if not entity:
            raise ValueError("UnitUser association not found")

        entity.role = role.value
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def upsert(
        self,
        unit_id: int,
        user_id: int,
        role: RoleName,
    ) -> UnitUser:
        """Create or update a UnitUser association."""
        existing = await self.get_by_unit_and_user(unit_id, user_id)

        if existing:
            # Only update if role changed
            if existing.role != role:
                return await self.update_role(unit_id, user_id, role)
            return existing
        else:
            return await self.create(unit_id, user_id, role)

    async def delete(self, unit_id: int, user_id: int) -> bool:
        """Delete a UnitUser association. Returns False if not found."""
        result = await self.session.exec(
            select(UnitUser).where(
                (UnitUser.user_id == user_id) & (UnitUser.unit_id == unit_id)
            )
        )
        entity = result.one_or_none()
        if not entity:
            return False

        await self.session.delete(entity)
        await self.session.commit()
        return True

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count UnitUser associations with optional filters."""
        query = select(func.count()).select_from(UnitUser)

        if filters:
            if "unit_id" in filters:
                query = query.where(UnitUser.unit_id == filters["unit_id"])
            if "user_id" in filters:
                query = query.where(UnitUser.user_id == filters["user_id"])
            if "role" in filters:
                query = query.where(UnitUser.role == filters["role"])

        result = await self.session.execute(query)
        return result.scalar_one()
