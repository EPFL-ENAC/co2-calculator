"""Integration tests for the traveler dropdown in the professional travel module.

The traveler dropdown is populated from ``GET /headcount/members``.  The
selected ``institutional_id`` is stored as ``user_institutional_id`` on
plane and train DataEntry records.

These tests cover the full chain:
- Headcount members are seeded in the DB.
- ``get_headcount_members`` returns them in dropdown-ready shape
  (``institutional_id``, ``name``).
- A plane or train DataEntry created with a ``user_institutional_id`` taken
  from that list passes schema validation and is persisted correctly.
- Train entries require ``origin_country_code`` / ``destination_country_code``
  for schema validation; omitting either raises a ``ValidationError``.
- ``get_member_by_institutional_id`` isolates a single member (used by the
  per-user filter in the endpoint).
"""

import pytest
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.modules.professional_travel.schemas import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelPlaneModuleHandler,
    ProfessionalTravelTrainHandlerCreate,
    ProfessionalTravelTrainModuleHandler,
)
from app.schemas.data_entry import DataEntryUpdate
from app.services.data_entry_service import DataEntryService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_report_and_modules(
    session: AsyncSession,
) -> tuple[CarbonReportModule, CarbonReportModule]:
    """Return (headcount_module, travel_module) seeded under a single report."""
    report = CarbonReport(year=2024, unit_id=1, overall_status=0)
    session.add(report)
    await session.flush()

    headcount_module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.headcount.value,
        status=ModuleStatus.NOT_STARTED,
    )
    travel_module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status=ModuleStatus.NOT_STARTED,
    )
    session.add(headcount_module)
    session.add(travel_module)
    await session.flush()
    return headcount_module, travel_module


async def _seed_member(
    session: AsyncSession,
    module_id: int,
    *,
    institutional_id: str,
    name: str,
) -> DataEntry:
    """Seed a headcount member DataEntry and return it."""
    entry = DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.member,
        status=DataEntryStatusEnum.PENDING,
        data={"user_institutional_id": institutional_id, "name": name},
    )
    session.add(entry)
    await session.flush()
    return entry


# ---------------------------------------------------------------------------
# Dropdown population
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_headcount_members_returns_dropdown_items(
    db_session: AsyncSession,
):
    """Members seeded in the headcount module appear in the dropdown list."""
    hc_module, _ = await _seed_report_and_modules(db_session)
    await _seed_member(
        db_session, hc_module.id, institutional_id="11111", name="Alice Dupont"
    )
    await _seed_member(
        db_session, hc_module.id, institutional_id="22222", name="Bob Martin"
    )
    await db_session.commit()

    service = DataEntryService(db_session)
    members = await service.get_headcount_members(carbon_report_module_id=hc_module.id)

    assert len(members) == 2
    iids = {m["institutional_id"] for m in members}
    assert iids == {"11111", "22222"}
    for m in members:
        assert "institutional_id" in m
        assert "name" in m


@pytest.mark.asyncio
async def test_get_headcount_members_ordered_by_name(
    db_session: AsyncSession,
):
    """Members are returned sorted alphabetically by name."""
    hc_module, _ = await _seed_report_and_modules(db_session)
    # Insert in reverse alphabetical order — result should still be A→Z.
    await _seed_member(db_session, hc_module.id, institutional_id="22222", name="Zara")
    await _seed_member(db_session, hc_module.id, institutional_id="11111", name="Alice")
    await db_session.commit()

    service = DataEntryService(db_session)
    members = await service.get_headcount_members(carbon_report_module_id=hc_module.id)

    names = [m["name"] for m in members]
    assert names == sorted(names), f"expected alphabetical order, got {names}"


@pytest.mark.asyncio
async def test_get_headcount_members_excludes_entries_without_institutional_id(
    db_session: AsyncSession,
):
    """Member entries lacking user_institutional_id are omitted from the dropdown."""
    hc_module, _ = await _seed_report_and_modules(db_session)

    # Valid member
    await _seed_member(db_session, hc_module.id, institutional_id="11111", name="Alice")
    # Entry without institutional_id — should be filtered out
    entry_no_iid = DataEntry(
        carbon_report_module_id=hc_module.id,
        data_entry_type_id=DataEntryTypeEnum.member,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Ghost"},  # no user_institutional_id key
    )
    db_session.add(entry_no_iid)
    await db_session.commit()

    service = DataEntryService(db_session)
    members = await service.get_headcount_members(carbon_report_module_id=hc_module.id)

    assert len(members) == 1
    assert members[0]["institutional_id"] == "11111"


@pytest.mark.asyncio
async def test_get_member_by_institutional_id_returns_correct_member(
    db_session: AsyncSession,
):
    """Fetching a single member by iid returns the right record."""
    hc_module, _ = await _seed_report_and_modules(db_session)
    await _seed_member(db_session, hc_module.id, institutional_id="11111", name="Alice")
    await _seed_member(db_session, hc_module.id, institutional_id="22222", name="Bob")
    await db_session.commit()

    service = DataEntryService(db_session)
    result = await service.get_member_by_institutional_id(
        carbon_report_module_id=hc_module.id,
        institutional_id="22222",
    )

    assert result is not None
    assert result["institutional_id"] == "22222"
    assert result["name"] == "Bob"


@pytest.mark.asyncio
async def test_get_member_by_institutional_id_returns_none_for_unknown_iid(
    db_session: AsyncSession,
):
    """Looking up an iid not in the headcount module returns None."""
    hc_module, _ = await _seed_report_and_modules(db_session)
    await _seed_member(db_session, hc_module.id, institutional_id="11111", name="Alice")
    await db_session.commit()

    service = DataEntryService(db_session)
    result = await service.get_member_by_institutional_id(
        carbon_report_module_id=hc_module.id,
        institutional_id="99999",
    )

    assert result is None


# ---------------------------------------------------------------------------
# Plane entry — schema validation and persistence
# ---------------------------------------------------------------------------


def test_plane_create_dto_accepts_user_institutional_id_from_dropdown():
    """ProfessionalTravelPlaneHandlerCreate validates with a dropdown-sourced iid."""
    dto = ProfessionalTravelPlaneHandlerCreate(
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        carbon_report_module_id=1,
        user_institutional_id="11111",
        origin_iata="GVA",
        destination_iata="JFK",
        cabin_class="economy",
        number_of_trips=1,
    )

    assert dto.user_institutional_id == "11111"
    assert dto.origin_iata == "GVA"
    assert dto.destination_iata == "JFK"
    assert dto.cabin_class == "economy"


def test_plane_create_dto_rejects_invalid_cabin_class():
    """Cabin class must be one of economy / business / first."""
    with pytest.raises(ValidationError):
        ProfessionalTravelPlaneHandlerCreate(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=1,
            user_institutional_id="11111",
            origin_iata="GVA",
            destination_iata="JFK",
            cabin_class="premium",
            number_of_trips=1,
        )


def test_plane_create_dto_rejects_eco_cabin_class():
    """'eco' (old abbreviation) is not accepted — the backend expects 'economy'.
    The frontend option value must be 'economy', not 'eco'."""
    with pytest.raises(ValidationError):
        ProfessionalTravelPlaneHandlerCreate(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=1,
            user_institutional_id="11111",
            origin_iata="GVA",
            destination_iata="JFK",
            cabin_class="eco",
            number_of_trips=1,
        )


def test_plane_create_dto_accepts_economy_cabin_class():
    """'economy' is the canonical value accepted by the backend validator."""
    dto = ProfessionalTravelPlaneHandlerCreate(
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        carbon_report_module_id=1,
        user_institutional_id="11111",
        origin_iata="GVA",
        destination_iata="JFK",
        cabin_class="economy",
        number_of_trips=1,
    )
    assert dto.cabin_class == "economy"


def test_plane_create_dto_rejects_zero_trips():
    with pytest.raises(ValidationError):
        ProfessionalTravelPlaneHandlerCreate(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=1,
            user_institutional_id="11111",
            origin_iata="GVA",
            destination_iata="JFK",
            cabin_class="economy",
            number_of_trips=0,
        )


@pytest.mark.asyncio
async def test_plane_entry_persisted_with_institutional_id_from_dropdown(
    db_session: AsyncSession,
):
    """A plane DataEntry seeded with user_institutional_id from the dropdown
    is retrievable via the submodule listing."""
    from app.repositories.data_entry_repo import DataEntryRepository

    hc_module, travel_module = await _seed_report_and_modules(db_session)
    await _seed_member(db_session, hc_module.id, institutional_id="11111", name="Alice")

    # Use the iid from the dropdown to create the travel entry
    entry = DataEntry(
        carbon_report_module_id=travel_module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={
            "user_institutional_id": "11111",
            "origin_iata": "GVA",
            "destination_iata": "JFK",
            "cabin_class": "economy",
            "number_of_trips": 2,
        },
    )
    db_session.add(entry)
    await db_session.commit()

    repo = DataEntryRepository(db_session)
    result = await repo.get_submodule_data(
        carbon_report_module_id=travel_module.id,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert result.count == 1
    assert result.items[0].user_institutional_id == "11111"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Train entry — schema validation and persistence
# ---------------------------------------------------------------------------


def test_train_create_dto_requires_origin_country_code():
    """Omitting origin_country_code raises a ValidationError."""
    with pytest.raises(ValidationError):
        ProfessionalTravelTrainHandlerCreate(
            data_entry_type_id=DataEntryTypeEnum.train.value,
            carbon_report_module_id=1,
            user_institutional_id="11111",
            origin_name="Geneva",
            destination_name="Zurich",
            # origin_country_code intentionally missing
            destination_country_code="CH",
            cabin_class="second",
            number_of_trips=1,
        )


def test_train_create_dto_requires_destination_country_code():
    """Omitting destination_country_code raises a ValidationError."""
    with pytest.raises(ValidationError):
        ProfessionalTravelTrainHandlerCreate(
            data_entry_type_id=DataEntryTypeEnum.train.value,
            carbon_report_module_id=1,
            user_institutional_id="11111",
            origin_name="Geneva",
            destination_name="Zurich",
            origin_country_code="CH",
            # destination_country_code intentionally missing
            cabin_class="second",
            number_of_trips=1,
        )


def test_train_create_dto_accepts_valid_country_codes():
    """Train entry with both country codes passes validation."""
    dto = ProfessionalTravelTrainHandlerCreate(
        data_entry_type_id=DataEntryTypeEnum.train.value,
        carbon_report_module_id=1,
        user_institutional_id="11111",
        origin_name="Geneva",
        destination_name="Zurich",
        origin_country_code="CH",
        destination_country_code="CH",
        cabin_class="second",
        number_of_trips=1,
    )

    assert dto.user_institutional_id == "11111"
    assert dto.origin_country_code == "CH"
    assert dto.destination_country_code == "CH"


def test_train_create_dto_accepts_row_country_code():
    """'RoW' is a valid country code for rest-of-world factors."""
    dto = ProfessionalTravelTrainHandlerCreate(
        data_entry_type_id=DataEntryTypeEnum.train.value,
        carbon_report_module_id=1,
        user_institutional_id="11111",
        origin_name="Nairobi",
        destination_name="Mombasa",
        origin_country_code="KE",
        destination_country_code="KE",
        cabin_class="first",
        number_of_trips=1,
    )
    assert dto.origin_country_code == "KE"


def test_train_create_dto_stores_country_code_verbatim():
    """DataEntryCreate does not validate country_code format — it is stored
    verbatim and validated downstream by the factor lookup / emission engine."""
    dto = ProfessionalTravelTrainHandlerCreate(
        data_entry_type_id=DataEntryTypeEnum.train.value,
        carbon_report_module_id=1,
        user_institutional_id="11111",
        origin_name="Geneva",
        destination_name="Zurich",
        # stored as-is; factor resolution will fall back to RoW
        origin_country_code="CHE",
        destination_country_code="CH",
        cabin_class="second",
        number_of_trips=1,
    )
    assert dto.data["origin_country_code"] == "CHE"


def test_train_create_dto_rejects_invalid_cabin_class():
    with pytest.raises(ValidationError):
        ProfessionalTravelTrainHandlerCreate(
            data_entry_type_id=DataEntryTypeEnum.train.value,
            carbon_report_module_id=1,
            user_institutional_id="11111",
            origin_name="Geneva",
            destination_name="Zurich",
            origin_country_code="CH",
            destination_country_code="CH",
            cabin_class="business",  # only first / second for train
            number_of_trips=1,
        )


@pytest.mark.asyncio
async def test_train_entry_persisted_with_institutional_id_and_country_codes(
    db_session: AsyncSession,
):
    """A train DataEntry with user_institutional_id from the dropdown and both
    country codes is stored correctly and retrievable."""
    from app.repositories.data_entry_repo import DataEntryRepository

    hc_module, travel_module = await _seed_report_and_modules(db_session)
    await _seed_member(db_session, hc_module.id, institutional_id="11111", name="Alice")

    entry = DataEntry(
        carbon_report_module_id=travel_module.id,
        data_entry_type_id=DataEntryTypeEnum.train,
        status=DataEntryStatusEnum.PENDING,
        data={
            "user_institutional_id": "11111",
            "origin_name": "Geneva",
            "destination_name": "Zurich",
            "origin_country_code": "CH",
            "destination_country_code": "CH",
            "cabin_class": "second",
            "number_of_trips": 1,
        },
    )
    db_session.add(entry)
    await db_session.commit()

    repo = DataEntryRepository(db_session)
    result = await repo.get_submodule_data(
        carbon_report_module_id=travel_module.id,
        data_entry_type_id=DataEntryTypeEnum.train.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert result.count == 1
    item = result.items[0]
    assert item.user_institutional_id == "11111"  # type: ignore[attr-defined]
    assert item.origin_name == "Geneva"  # type: ignore[attr-defined]
    assert item.destination_name == "Zurich"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Cross-module: dropdown member → travel entry linkage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dropdown_iid_matches_travel_entry_iid(
    db_session: AsyncSession,
):
    """The institutional_id returned by the dropdown matches the
    user_institutional_id stored in the travel entry — verifying the end-to-end
    linking between headcount and travel modules."""
    hc_module, travel_module = await _seed_report_and_modules(db_session)
    await _seed_member(
        db_session, hc_module.id, institutional_id="33333", name="Charlie"
    )

    # Simulate the UI flow: fetch dropdown, pick a traveler, submit the form.
    service = DataEntryService(db_session)
    members = await service.get_headcount_members(carbon_report_module_id=hc_module.id)
    assert len(members) == 1
    selected_iid = members[0]["institutional_id"]  # "33333"

    # Submit a plane entry using the selected iid
    entry = DataEntry(
        carbon_report_module_id=travel_module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={
            "user_institutional_id": selected_iid,
            "origin_iata": "CDG",
            "destination_iata": "LHR",
            "cabin_class": "business",
            "number_of_trips": 1,
        },
    )
    db_session.add(entry)
    await db_session.commit()

    from app.repositories.data_entry_repo import DataEntryRepository

    repo = DataEntryRepository(db_session)
    result = await repo.get_submodule_data(
        carbon_report_module_id=travel_module.id,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert result.count == 1
    stored_iid = result.items[0].user_institutional_id  # type: ignore[attr-defined]
    assert stored_iid == selected_iid, (
        f"Travel entry iid {stored_iid!r} does not match "
        f"dropdown selection {selected_iid!r}"
    )


# ---------------------------------------------------------------------------
# PATCH: validate_update with existing data merged (regression for slash dates)
# ---------------------------------------------------------------------------
# When a departure_date was entered with slashes (e.g. "2026/01/19") the value
# is stored verbatim in DataEntry.data.  A partial PATCH (e.g. number_of_trips)
# merges existing_data into the update_payload; the Update DTO must normalise
# the slash date or validation raises a 400.


def test_plane_patch_validate_update_with_slash_date():
    """Plane PATCH with a slash-formatted departure_date from existing data must
    not raise a ValidationError (regression for missing DepartureDateMixin)."""
    existing_data = {
        "user_institutional_id": "12345",
        "origin_iata": "GVA",
        "destination_iata": "JFK",
        "cabin_class": "economy",
        "departure_date": "2026/01/19",  # slash format stored by the UI
        "number_of_trips": 3,
        "primary_factor_id": None,
    }
    update_payload = {
        **existing_data,
        "number_of_trips": 10,
        "data_entry_type_id": DataEntryTypeEnum.plane.value,
        "carbon_report_module_id": 1,
    }
    handler = ProfessionalTravelPlaneModuleHandler()
    validated = handler.validate_update(update_payload)
    assert validated.departure_date is not None
    from datetime import date

    assert validated.departure_date == date(2026, 1, 19)


def test_train_patch_validate_update_with_slash_date():
    """Train PATCH with a slash-formatted departure_date from existing data must
    not raise a ValidationError (regression for missing DepartureDateMixin)."""
    existing_data = {
        "user_institutional_id": "12345",
        "origin_name": "Geneva",
        "destination_name": "Paris",
        "origin_country_code": "CH",
        "destination_country_code": "FR",
        "origin_natural_key": "geneva_ch",
        "destination_natural_key": "paris_fr",
        "cabin_class": "second",
        "departure_date": "2026/01/19",  # slash format
        "number_of_trips": 3,
        "primary_factor_id": None,
    }
    update_payload = {
        **existing_data,
        "number_of_trips": 10,
        "data_entry_type_id": DataEntryTypeEnum.train.value,
        "carbon_report_module_id": 1,
    }
    handler = ProfessionalTravelTrainModuleHandler()
    validated = handler.validate_update(update_payload)
    assert validated.departure_date is not None
    from datetime import date

    assert validated.departure_date == date(2026, 1, 19)


def test_plane_patch_validate_update_no_departure_date():
    """Plane PATCH with no departure_date in the PATCH payload (number_of_trips only)
    and no departure_date in existing data succeeds without a date error."""
    existing_data = {
        "user_institutional_id": "12345",
        "origin_iata": "GVA",
        "destination_iata": "JFK",
        "cabin_class": "economy",
        "number_of_trips": 3,
        "primary_factor_id": None,
    }
    update_payload = {
        **existing_data,
        "number_of_trips": 10,
        "data_entry_type_id": DataEntryTypeEnum.plane.value,
        "carbon_report_module_id": 1,
    }
    handler = ProfessionalTravelPlaneModuleHandler()
    validated = handler.validate_update(update_payload)
    assert validated.number_of_trips == 10
    assert validated.departure_date is None


def test_plane_patch_produces_valid_data_entry_update():
    """Full PATCH pipeline: validate_update → model_dump → DataEntryUpdate
    succeeds and the final data dict contains the updated number_of_trips."""
    existing_data = {
        "user_institutional_id": "12345",
        "origin_iata": "GVA",
        "destination_iata": "JFK",
        "cabin_class": "economy",
        "departure_date": "2026/01/19",
        "number_of_trips": 3,
        "primary_factor_id": None,
    }
    update_payload = {
        **existing_data,
        "number_of_trips": 10,
        "data_entry_type_id": DataEntryTypeEnum.plane.value,
        "carbon_report_module_id": 1,
    }
    handler = ProfessionalTravelPlaneModuleHandler()
    validated = handler.validate_update(update_payload)
    data_entry_update = DataEntryUpdate(**validated.model_dump(exclude_unset=True))
    final = data_entry_update.model_dump(exclude_unset=True)
    assert final["data"]["number_of_trips"] == 10
