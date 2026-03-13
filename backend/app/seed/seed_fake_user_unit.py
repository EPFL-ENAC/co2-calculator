import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.user import RoleScope, User, UserProvider
from app.providers.test_fixtures import TEST_ROLES, TEST_UNITS, TEST_USERS
from app.schemas.unit import UnitRead
from app.schemas.user import UserRead
from app.services.unit_service import UnitService
from app.services.unit_user_service import UnitUserService
from app.services.user_service import UserService

logger = get_logger(__name__)
settings = get_settings()


async def seed_test_users(session: AsyncSession) -> None:
    """Seed all test users from centralized fixtures."""
    logger.info("Seeding test user records...")
    user_service = UserService(session)
    for role_name, user_data in TEST_USERS.items():
        await user_service.upsert_user(
            id=None,
            email=user_data["email"],
            institutional_id=user_data["institutional_id"],
            display_name=user_data["display_name"],
            roles=[],
            stop_recursion=True,
            provider=UserProvider.TEST,
        )


async def seed_test_units(session: AsyncSession) -> None:
    """Seed all test units from centralized fixtures."""
    logger.info("Seeding test unit records...")
    unit_service = UnitService(session)
    for unit in TEST_UNITS:
        await unit_service.upsert(unit_data=unit.model_copy())


async def seed_unit_users(session: AsyncSession) -> None:
    """Seed unit-user relationships derived from TEST_ROLES and TEST_USERS."""
    logger.info("Seeding unit_user relationships...")
    unit_user_service = UnitUserService(session)
    user_service = UserService(session)
    unit_service = UnitService(session)

    for role_name, roles in TEST_ROLES.items():
        user_data = TEST_USERS[role_name]
        user_row: User | None = await user_service.get_by_code(
            user_data["institutional_id"]
        )
        if not user_row or not user_row.id:
            logger.warning(
                "Cannot seed unit_user: user not found",
                extra={"role": role_name.value},
            )
            continue
        user = UserRead(**user_row.model_dump())

        for role in roles:
            # Only unit-scoped roles create unit_user associations
            if not isinstance(role.on, RoleScope) or not role.on.institutional_id:
                continue
            unit_iid = role.on.institutional_id
            unit_read: UnitRead | None = await unit_service.get_by_institutional_id(
                unit_iid
            )
            if not unit_read or not unit_read.id:
                logger.warning(
                    "Cannot seed unit_user: unit not found",
                    extra={"institutional_id": unit_iid},
                )
                continue
            await unit_user_service.upsert(
                unit_id=unit_read.id,
                user_id=user.id,
                role=role_name,
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
