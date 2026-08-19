"""Member role uniqueness is enforced by the database (#2050 J4).

The pre-check it replaces was both a statement and a check-then-act race: two
concurrent POSTs could both pass it and both insert.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum

pytestmark = pytest.mark.asyncio


async def test_duplicate_member_role_is_rejected_by_the_database(
    pg_dsn, make_unit, make_carbon_report, make_carbon_report_module
):
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as session:
            unit = await make_unit(session)
            report = await make_carbon_report(session, unit_id=unit.id, year=2025)
            module = await make_carbon_report_module(
                session,
                carbon_report_id=report.id,
                module_type_id=ModuleTypeEnum.headcount.value,
            )
            await session.commit()
            module_id = module.id

        def _member(**data):
            return DataEntry(
                carbon_report_module_id=module_id,
                data_entry_type_id=DataEntryTypeEnum.member.value,
                data={"name": "A", "fte": 1.0, **data},
            )

        async with Sf() as session:
            session.add(_member(user_institutional_id="M-1", sius_code="51"))
            await session.commit()

        # Same person, same role, same module → rejected.
        with pytest.raises(IntegrityError):
            async with Sf() as session:
                session.add(_member(user_institutional_id="M-1", sius_code="51"))
                await session.commit()

        # Same person, a *different* role → allowed (#951: a person can hold
        # several roles in one unit).
        async with Sf() as session:
            session.add(_member(user_institutional_id="M-1", sius_code="62"))
            await session.commit()

        # A student carrying the same pair is untouched by the member-only index.
        async with Sf() as session:
            session.add(
                DataEntry(
                    carbon_report_module_id=module_id,
                    data_entry_type_id=DataEntryTypeEnum.student.value,
                    data={
                        "user_institutional_id": "M-1",
                        "sius_code": "51",
                        "fte": 1.0,
                    },
                )
            )
            await session.commit()

        # And a member row with no institutional id at all is outside the index.
        async with Sf() as session:
            session.add_all(
                [
                    _member(sius_code="51"),
                    _member(sius_code="51"),
                ]
            )
            await session.commit()
    finally:
        await engine.dispose()
