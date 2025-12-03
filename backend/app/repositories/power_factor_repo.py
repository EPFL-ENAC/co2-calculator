from typing import List

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.emission_factor import PowerFactor


class PowerFactorRepository:
    async def list_classes(self, session: AsyncSession, submodule: str) -> List[str]:
        stmt = (
            select(col(PowerFactor.equipment_class))
            .where(col(PowerFactor.submodule) == submodule)
            .distinct()
            .order_by(col(PowerFactor.equipment_class))
        )
        result = await session.execute(stmt)
        return [row for row in result.scalars().all() if row is not None]

    async def list_subclasses(
        self, session: AsyncSession, submodule: str, equipment_class: str
    ) -> List[str]:
        stmt = (
            select(col(PowerFactor.sub_class))
            .where(col(PowerFactor.submodule) == submodule)
            .where(col(PowerFactor.equipment_class) == equipment_class)
            .where(col(PowerFactor.sub_class).is_not(None))
            .distinct()
            .order_by(col(PowerFactor.sub_class))
        )
        result = await session.execute(stmt)
        return [row for row in result.scalars().all() if row is not None]
