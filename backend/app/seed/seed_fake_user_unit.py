import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.unit import Unit
from app.models.user import RoleName, User, UserProvider
from app.schemas.unit import UnitRead
from app.schemas.user import UserRead
from app.services.unit_service import UnitService
from app.services.unit_user_service import UnitUserService
from app.services.user_service import UserService

logger = get_logger(__name__)
settings = get_settings()


async def seed_test_users(session: AsyncSession) -> None:
    # upsert user with provider code 44444 for testing
    logger.info("Seeding test user records...")
    user_service = UserService(session)
    await user_service.upsert_user(
        id=None,
        email="testuser@testdomain.epfl",
        provider_code="44444",
        display_name="Test User",
        roles=[],
        stop_recursion=True,
        provider=UserProvider.DEFAULT,
    )
    await user_service.upsert_user(
        id=None,
        email="headOfUnit@testdomain.epfl",
        provider_code="777777",
        display_name="Test User Head of Unit",
        roles=[],
        stop_recursion=True,
        provider=UserProvider.DEFAULT,
    )


async def seed_test_units(session: AsyncSession) -> None:
    # upsert unit ids 10208 and 12345 for testing
    logger.info("Seeding equipment records...")
    unit_service = UnitService(session)
    await unit_service.upsert(
        unit_data=Unit(
            provider_code="12345",
            name="test unit 12345",
            principal_user_provider_code="777777",
        )
    )
    await unit_service.upsert(
        unit_data=Unit(
            provider_code="10208",
            name="enac test 10208",
            principal_user_provider_code="777777",
        )
    )


async def seed_unit_users(session: AsyncSession) -> None:
    logger.info("Seeding unit_user relationships...")
    unit_user_service = UnitUserService(session)
    # link user 44444 to unit 10208
    unit_10208: UnitRead | None = await UnitService(session).get_by_provider_code(
        "10208"
    )
    unit_12345: UnitRead | None = await UnitService(session).get_by_provider_code(
        "12345"
    )
    if unit_10208 is None or unit_12345 is None:
        logger.error("Cannot seed unit_user relationships: missing unit")
        return
    user_row: User | None = await UserService(session).get_by_code("44444")
    user: UserRead | None = None
    if user_row:
        user = UserRead(**user_row.model_dump())
    user_principal_row: User | None = await UserService(session).get_by_code("777777")
    user_principal: UserRead | None = None
    if user_principal_row:
        user_principal = UserRead(**user_principal_row.model_dump())
    if unit_10208 is None or user is None or user_principal is None:
        logger.error("Cannot seed unit_user relationships: missing unit or user")
        return
    await unit_user_service.upsert(
        unit_id=unit_10208.id,
        user_id=user.id,
        role=RoleName.CO2_USER_STD,
    )
    # link user 777777 to unit 10208 as head_of_unit
    await unit_user_service.upsert(
        unit_id=unit_10208.id,
        user_id=user_principal.id,
        role=RoleName.CO2_USER_PRINCIPAL,
    )
    # link user 777777 to unit 12345 as head_of_unit
    await unit_user_service.upsert(
        unit_id=unit_12345.id,
        user_id=user_principal.id,
        role=RoleName.CO2_USER_PRINCIPAL,
    )


async def main() -> None:
    """Main seed function."""
    logger.info("Starting equipment and emissions seeding...")

    async with SessionLocal() as session:
        await seed_test_users(session)
        await seed_test_units(session)
        await seed_unit_users(session)
        # Commit all changes at the end of the seeding process,
        # after seeding users, units, and unit_user relationships
        await session.commit()
        # seed unit_users relationships

    logger.info("Equipment and emissions seeding complete!")


if __name__ == "__main__":
    # run script on /app/api/v1/synth_data.csv
    asyncio.run(main())
