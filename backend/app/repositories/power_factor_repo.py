from typing import Dict, List

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

    async def get_power_factor(
        self,
        session: AsyncSession,
        submodule: str,
        equipment_class: str,
        sub_class: str | None,
    ) -> PowerFactor | None:
        # Prefer exact subclass match when provided,
        # otherwise fallback to class-level match
        stmt = (
            select(PowerFactor)
            .where(col(PowerFactor.submodule) == submodule)
            .where(col(PowerFactor.equipment_class) == equipment_class)
            .order_by(col(PowerFactor.valid_from).desc())
        )
        if sub_class:
            stmt = stmt.where(col(PowerFactor.sub_class) == sub_class)

        result = await session.execute(stmt)
        first = result.scalars().first()
        if first:
            return first

        # Fallback to class-only if subclass not found or not provided
        fallback_stmt = (
            select(PowerFactor)
            .where(col(PowerFactor.submodule) == submodule)
            .where(col(PowerFactor.equipment_class) == equipment_class)
            .where(col(PowerFactor.sub_class).is_(None))
            .order_by(col(PowerFactor.valid_from).desc())
        )
        fb_result = await session.execute(fallback_stmt)
        return fb_result.scalars().first()

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

    async def get_class_subclass_map(
        self, session: AsyncSession, submodule: str
    ) -> Dict[str, List[str]]:
        """Return a mapping of equipment_class -> list of subclasses for a submodule.

        - All classes for the submodule are included as keys.
        - Classes without any subclasses are mapped to an empty list.
        - Only non-null subclasses are included in the lists.
        """

        # Start from the full class list so classes without subclasses
        # still appear in the mapping.
        classes = await self.list_classes(session, submodule)
        mapping: Dict[str, List[str]] = {cls: [] for cls in classes}

        # Fetch all (class, subclass) pairs with a non-null subclass
        stmt = (
            select(col(PowerFactor.equipment_class), col(PowerFactor.sub_class))
            .where(col(PowerFactor.submodule) == submodule)
            .where(col(PowerFactor.sub_class).is_not(None))
        )
        result = await session.execute(stmt)

        for equipment_class, sub_class in result.all():
            if equipment_class is None or sub_class is None:
                continue
            if equipment_class not in mapping:
                mapping[equipment_class] = []
            if sub_class not in mapping[equipment_class]:
                mapping[equipment_class].append(sub_class)

        # Sort subclasses for deterministic ordering
        for key in mapping:
            mapping[key].sort()

        return mapping
