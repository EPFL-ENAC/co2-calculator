from typing import Dict, List

from sqlmodel.ext.asyncio.session import AsyncSession

from app.repositories.power_factor_repo import PowerFactorRepository


class PowerFactorService:
    def __init__(self, repo: PowerFactorRepository | None = None):
        self.repo = repo or PowerFactorRepository()

    async def get_classes(self, session: AsyncSession, submodule: str) -> List[str]:
        return await self.repo.list_classes(session, submodule)

    async def get_subclasses(
        self, session: AsyncSession, submodule: str, equipment_class: str
    ) -> List[str]:
        return await self.repo.list_subclasses(session, submodule, equipment_class)

    async def get_power_factor(
        self,
        session: AsyncSession,
        submodule: str,
        equipment_class: str,
        sub_class: str | None,
    ):
        return await self.repo.get_power_factor(
            session, submodule, equipment_class, sub_class
        )

    async def get_class_subclass_map(
        self, session: AsyncSession, submodule: str
    ) -> Dict[str, List[str]]:
        return await self.repo.get_class_subclass_map(session, submodule)
