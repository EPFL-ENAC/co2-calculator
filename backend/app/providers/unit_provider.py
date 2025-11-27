from abc import ABC, abstractmethod
from typing import List

from sqlmodel import Session, select

from app.models.unit import Unit


class UnitProvider(ABC):
    @abstractmethod
    async def get_units(self) -> List[Unit]:
        pass


class LocalUnitProvider(UnitProvider):
    def __init__(self, session: Session):
        self.session = session

    async def get_units(self) -> List[Unit]:
        statement = select(Unit)
        results = self.session.exec(statement)
        return list(results.all())


class APIUnitProvider(UnitProvider):
    def __init__(self, api_url: str):
        self.api_url = api_url

    async def get_units(self) -> List[Unit]:
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(f"{self.api_url}/units?include_users=true")
        #     response.raise_for_status()
        #     units_data = response.json()
        #     units = []
        #     for data in units_data:
        #         # Map users if present in API response
        #         users_data = data.pop("users", [])
        #         unit = Unit(**data)
        #         unit.users = [User(**u) for u in users_data]
        #         units.append(unit)
        #     return units
        return []  # Placeholder for API call


def get_unit_provider(source: str, **kwargs) -> UnitProvider:
    if source == "local":
        return LocalUnitProvider(kwargs["session"])
    elif source == "api":
        return APIUnitProvider(kwargs["api_url"])
    else:
        raise ValueError("Unknown unit provider source")
