"""Resource repository for database operations."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.unit import Unit

units_mock = [
    {
        "id": "12345",
        "name": "ENAC-IT4R",
        "role": "co2.user.principal",
        "principal_user_id": "67890",
        "principal_user_name": "Alice",
        "principal_user_function": "Professor",
        "affiliations": ["ENAC", "ENAC-IT"],
    },
    {
        "id": "22222",
        "name": "LCH",
        "role": "co2.user.principal",
        "principal_user_id": "67890",
        "principal_user_name": "Alice",
        "principal_user_function": "Professor",
        "affiliations": ["ENAC"],
    },
    {
        "id": "67890",
        "name": "ALICE",
        "role": "co2.user.secondary",
        "principal_user_id": "67890",
        "principal_user_name": "Alice",
        "principal_user_function": "Professor",
        "affiliations": ["ENAC", "SV"],
    },
    {
        "id": "11111",
        "name": "LaSUR",
        "role": "co2.user.std",
        "principal_user_id": "54321",
        "principal_user_name": "Bob",
        "principal_user_function": "Researcher",
        "affiliations": ["ENAC"],
    },
]


async def get_unit_by_id(db: AsyncSession, unit_id: int) -> Optional[Unit]:
    """Get unit by ID."""
    for item in units_mock:
        if item["id"] == unit_id:
            return item  # type: ignore
    return None


async def get_units(
    db: AsyncSession, skip: int = 0, limit: int = 100, filters: Optional[dict] = None
) -> List[Unit]:
    """Get list of units with optional filters."""
    # For demonstration, we ignore db and filters and return mock data
    # Should sort by "role": "co2.user.principal",
    # first then "co2.user.secondary", then "co2.user.std"
    role_priority = {
        "co2.user.principal": 1,
        "co2.user.secondary": 2,
        "co2.user.std": 3,
    }
    units_mock_sorted = sorted(
        units_mock, key=lambda x: role_priority.get(str(x["role"]), 99)
    )
    return units_mock_sorted[skip : skip + limit]  # type: ignore


async def upsert_unit(db: AsyncSession, unit_id: str) -> Unit:
    """Upsert unit (internal operation)."""
    # Check if unit exists
    query = select(Unit).where(Unit.id == unit_id)
    result = await db.execute(query)
    unit = result.scalars().first()

    if unit:
        # Unit already exists, just return it
        return unit

    # Create new unit if it doesn't exist
    now = datetime.utcnow()
    new_unit = Unit(
        id=unit_id,
        name=f"Unit {unit_id}",
        visibility="private",
        affiliations=[],
        created_at=now,
        updated_at=now,
        created_by=None,
        updated_by=None,
    )
    db.add(new_unit)
    await db.flush()  # Flush to ensure it's in the DB before the commit

    return new_unit
