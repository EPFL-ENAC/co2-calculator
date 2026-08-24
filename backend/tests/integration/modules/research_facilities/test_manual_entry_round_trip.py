"""#2007 — a manually added research-facility row must actually compute.

The rest of the #2007 coverage stops at boundaries: the frontend specs mock the
API, and the workflow unit tests mock the services. Nothing showed that a
hand-entered row resolves its factor and produces a number — the whole point of
the feature. This drives the real workflow, service and repo stack against the
integration fixture's database (in-memory SQLite), so factor resolution and the
emission formula run for real rather than being mocked.

The formula is a share of the platform's own footprint:
``kg = use / total_use * kg_co2eq_sum``. CAM-GE reports in ``%`` with
``total_use = 100``, so 40% of a 5000 kg platform is 2000 kg.
"""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.modules.emissions import EmissionType
from app.schemas.carbon_report import CarbonReportModuleRead
from app.schemas.user import UserRead
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow

_USER = UserRead(
    id=1,
    display_name="Principal",
    email="principal@example.org",
    provider=UserProvider.TEST,
    institutional_id="352707",
)


async def _seed_module(session: AsyncSession, year: int = 2025) -> CarbonReportModule:
    report = CarbonReport(year=year, unit_id=1, overall_status=0)
    session.add(report)
    await session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.research_facilities.value,
        status=ModuleStatus.NOT_STARTED,
    )
    session.add(module)
    await session.flush()
    return module


async def _emission_of(session: AsyncSession, entry_id: int) -> DataEntryEmission:
    session.expire_all()
    return (
        await session.execute(
            select(DataEntryEmission).where(DataEntryEmission.data_entry_id == entry_id)
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_manual_common_facility_entry_computes_its_share(
    db_session: AsyncSession,
):
    module = await _seed_module(db_session)
    db_session.add(
        Factor(
            emission_type_id=EmissionType.research_facilities__facilities.value,
            data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
            classification={
                "researchfacility_id": "0872",
                "researchfacility_name": "CAM-GE",
            },
            values={"use_unit": "%", "total_use": 100, "kg_co2eq_sum": 5000.0},
            year=2025,
        )
    )
    await db_session.commit()

    workflow = CarbonReportModuleWorkflow(db_session)
    created = await workflow.create(
        carbon_report_module=CarbonReportModuleRead.model_validate(
            module, from_attributes=True
        ),
        data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
        # Exactly what ModuleForm.buildPayload sends: the id identifies the
        # factor, the name and unit ride along mirrored from it.
        item_data={
            "researchfacility_id": "0872",
            "researchfacility_name": "CAM-GE",
            "use": 40,
            "use_unit": "%",
        },
        current_user=_USER,
        request_context={},
        background_tasks=_NoopBackgroundTasks(),
    )

    emission = await _emission_of(db_session, created.id)
    assert emission.kg_co2eq == pytest.approx(2000.0)

    db_session.expire_all()
    stored = (
        await db_session.execute(select(DataEntry).where(DataEntry.id == created.id))
    ).scalar_one()
    # #951 provenance: a manual row is the user's own, so it stays editable
    # and deletable.
    assert stored.source == DataEntrySourceEnum.USER_MANUAL.value
    assert stored.created_by_id == _USER.id
    # Derived values resolve from the factor and must not be denormalized in.
    assert "kg_co2eq" not in stored.data


@pytest.mark.asyncio
async def test_manual_animal_facility_entry_sums_its_source_shares(
    db_session: AsyncSession,
):
    module = await _seed_module(db_session)
    db_session.add(
        Factor(
            emission_type_id=EmissionType.research_facilities__animal__rodent.value,
            data_entry_type_id=DataEntryTypeEnum.animal_facilities.value,
            classification={
                "researchfacility_id": "1321",
                "researchfacility_name": "CPG",
                "researchfacility_type": "rodent",
            },
            values={
                "use_unit": "housings",
                "total_use": 4000,
                "kg_co2eq_sum_processemissions": 1000.0,
                "kg_co2eq_sum_building_energycombustions": 2000.0,
                "kg_co2eq_sum_building_rooms": 3000.0,
                "kg_co2eq_sum_purchases_common": 0.0,
                "kg_co2eq_sum_purchases_additional": 0.0,
                "kg_co2eq_sum_equipments": 4000.0,
            },
            year=2025,
        )
    )
    await db_session.commit()

    workflow = CarbonReportModuleWorkflow(db_session)
    created = await workflow.create(
        carbon_report_module=CarbonReportModuleRead.model_validate(
            module, from_attributes=True
        ),
        data_entry_type_id=DataEntryTypeEnum.animal_facilities.value,
        item_data={
            "researchfacility_id": "1321",
            "researchfacility_name": "CPG",
            "researchfacility_type": "rodent",
            "use": 1000,
            "use_unit": "housings",
        },
        current_user=_USER,
        request_context={},
        background_tasks=_NoopBackgroundTasks(),
    )

    # 1000/4000 of (1000 + 2000 + 3000 + 0 + 0 + 4000).
    emission = await _emission_of(db_session, created.id)
    assert emission.kg_co2eq == pytest.approx(2500.0)


@pytest.mark.asyncio
async def test_a_unit_that_disagrees_with_the_factor_is_refused(
    db_session: AsyncSession,
):
    """Why `use_unit` is mirrored read-only rather than typed: the formula
    cannot resolve a unit the factor does not use, and since #2050 J1 that
    raises rather than silently dropping the row.
    """
    module = await _seed_module(db_session)
    db_session.add(
        Factor(
            emission_type_id=EmissionType.research_facilities__facilities.value,
            data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
            classification={
                "researchfacility_id": "1902",
                "researchfacility_name": "SCITAS-GE",
            },
            values={"use_unit": "CHF", "total_use": 1000.0, "kg_co2eq_sum": 500.0},
            year=2025,
        )
    )
    await db_session.commit()

    workflow = CarbonReportModuleWorkflow(db_session)
    with pytest.raises(Exception) as exc_info:
        await workflow.create(
            carbon_report_module=CarbonReportModuleRead.model_validate(
                module, from_attributes=True
            ),
            data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
            item_data={
                "researchfacility_id": "1902",
                "researchfacility_name": "SCITAS-GE",
                "use": 100,
                "use_unit": "hours",
            },
            current_user=_USER,
            request_context={},
            background_tasks=_NoopBackgroundTasks(),
        )
    assert "hours" in str(exc_info.value) or "unit" in str(exc_info.value).lower()


class _NoopBackgroundTasks:
    """FastAPI's BackgroundTasks without a response cycle to run them."""

    def add_task(self, *args: object, **kwargs: object) -> None:
        return None
