"""``scripts/normalize_join_keys.py`` against real Postgres (#1489, #2592).

Old-style factor and entry rows are seeded, the audit must report exactly
them, ``apply`` must rewrite them into the DTO form without touching other
keys, non-strings or unmapped entry types, and a second audit must find
nothing. When two factors would collide after normalization the script
refuses to write anything: merging is a manual decision.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from scripts import normalize_join_keys as script

from .conftest import seeded_year_with_units

_YEAR = 2025
_ENTRIES: dict[str, tuple[DataEntryTypeEnum, dict]] = {
    "purchase": (
        DataEntryTypeEnum.consumable_accessories,
        {
            "name": " Pipette ",
            "currency": "CHF",
            "purchase_institutional_code": " 51100000 ",
            "purchase_additional_code": "  ",
            "total_spent_amount": 10,
            "note": "  keep  ",
        },
    ),
    "train": (
        DataEntryTypeEnum.train,
        {
            "origin_name": " Lausanne ",
            "destination_name": "Lyon",
            "origin_country_code": " ch ",
            "destination_country_code": "row",
            "cabin_class": " Second ",
        },
    ),
    "facility": (
        DataEntryTypeEnum.research_facilities,
        {"researchfacility_id": 1.0, "researchfacility_name": " Lab ", "use": 10},
    ),
    "member": (DataEntryTypeEnum.member, {"name": " X ", "sius_code": " 51 "}),
}
_EXPECTED: dict[str, dict] = {
    "purchase": {
        "name": "Pipette",
        "currency": "chf",
        "purchase_institutional_code": "51100000",
        "purchase_additional_code": None,
        "total_spent_amount": 10,
        "note": "  keep  ",
    },
    "train": {
        "origin_name": "Lausanne",
        "destination_name": "Lyon",
        "origin_country_code": "CH",
        "destination_country_code": "RoW",
        "cabin_class": "second",
    },
    "facility": {"researchfacility_id": "1", "researchfacility_name": "Lab", "use": 10},
    "member": {"name": " X ", "sius_code": " 51 "},
}


def _factor(det: DataEntryTypeEnum, classification: dict) -> Factor:
    return Factor(
        emission_type_id=10000,
        data_entry_type_id=det.value,
        classification=classification,
        values={"ef": 0.5},
        year=_YEAR,
    )


async def _seed(session_factory, factors: list[Factor]) -> dict[str, int]:
    async with session_factory() as s:
        seeded = await seeded_year_with_units(s, year=_YEAR, n_units=1)
        crm = seeded.modules_by_unit_and_type[
            (seeded.units[0].id, int(ModuleTypeEnum.purchase))
        ]
        entries = {
            label: DataEntry(
                data_entry_type_id=det.value,
                carbon_report_module_id=crm.id,
                data=data,
            )
            for label, (det, data) in _ENTRIES.items()
        }
        s.add_all(list(entries.values()) + factors)
        await s.commit()
        return {label: e.id for label, e in entries.items()}


async def _read(session_factory, ids: dict[str, int]) -> dict[str, dict]:
    async with session_factory() as s:
        return {
            label: (await s.get(DataEntry, entry_id)).data
            for label, entry_id in ids.items()
        }


@pytest.mark.asyncio
async def test_apply_rewrites_reported_rows_and_is_idempotent(pg_dsn):
    engine = create_async_engine(pg_dsn, future=True)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        noisy = _factor(DataEntryTypeEnum.train, {"country_code": " fr "})
        clean = _factor(DataEntryTypeEnum.train, {"country_code": "RoW"})
        ids = await _seed(sf, [noisy, clean])

        async with engine.begin() as conn:
            report = await script.audit(conn)
            assert report.factors_scanned == 2
            assert report.factor_rewrites == {noisy.id: {"country_code": "FR"}}
            assert report.duplicate_groups == []
            assert set(report.entry_rewrites) == {
                ids["purchase"],
                ids["train"],
                ids["facility"],
            }
            assert report.rejected == []
            await script.apply(conn, report)

        assert await _read(sf, ids) == _EXPECTED
        async with sf() as s:
            assert (await s.get(Factor, noisy.id)).classification == {
                "country_code": "FR"
            }

        async with engine.connect() as conn:
            again = await script.audit(conn)
        assert again.factor_rewrites == {} and again.entry_rewrites == {}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_apply_refuses_when_factor_identities_collide(pg_dsn):
    engine = create_async_engine(pg_dsn, future=True)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        upper = _factor(DataEntryTypeEnum.train, {"country_code": "FR"})
        lower = _factor(DataEntryTypeEnum.train, {"country_code": "fr"})
        ids = await _seed(sf, [upper, lower])

        async with engine.begin() as conn:
            report = await script.audit(conn)
            assert report.duplicate_groups == [sorted([upper.id, lower.id])]
            with pytest.raises(ValueError, match="collide"):
                await script.apply(conn, report)

        stored = await _read(sf, ids)
        assert stored["purchase"]["currency"] == "CHF", "nothing written on refusal"
    finally:
        await engine.dispose()
