"""Buildings CSV rows with an unknown room are rejected, in bulk (#2253).

``enrich_csv_row`` runs once per CSV row; the original check did one
``building_rooms`` SELECT per row. The known-room set now loads once per
session (cached on ``session.info``), so an N-row file costs one query.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.buildings.handlers import (
    BuildingEmbodiedEnergyModuleHandler,
    BuildingRoomModuleHandler,
)


class _ForbiddenSession:
    """Sentinel session: any attribute access means the check wrongly
    reached the DB instead of rejecting the row on the missing room_name.
    """

    def __getattr__(self, name: str):
        raise AssertionError(
            f"room lookup must not run when room_name is missing "
            f"(accessed session.{name})"
        )


class _FakeSession:
    """Session double with the real ``info`` dict the cache lives on."""

    def __init__(self) -> None:
        self.info: dict = {}


@pytest.mark.asyncio
async def test_missing_room_name_is_rejected_without_touching_the_db() -> None:
    handler = BuildingRoomModuleHandler()
    data = {"building_name": "BC"}

    enriched, err = await handler.enrich_csv_row(data, _ForbiddenSession())

    assert err == "Missing room_name"
    assert enriched == data


@pytest.mark.asyncio
async def test_unknown_room_is_a_hard_row_error() -> None:
    handler = BuildingRoomModuleHandler()
    data = {"building_name": "ZZ", "room_name": "ZZ99"}

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        mock_service_cls.return_value.get_room_names = AsyncMock(return_value={"BC01"})
        enriched, err = await handler.enrich_csv_row(data, _FakeSession())

    assert err is not None
    assert "ZZ99" in err
    assert "not found in the building rooms reference" in err
    assert enriched == data


@pytest.mark.asyncio
async def test_known_room_passes_with_data_unchanged() -> None:
    handler = BuildingRoomModuleHandler()
    data = {"building_name": "BC", "room_name": "BC01"}

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        mock_service_cls.return_value.get_room_names = AsyncMock(return_value={"BC01"})
        enriched, err = await handler.enrich_csv_row(data, _FakeSession())

    assert err is None
    assert enriched == data


@pytest.mark.asyncio
async def test_many_rows_and_both_handlers_share_one_query_per_session() -> None:
    """The point of the batching: N rows → a single room-names query."""
    rooms_handler = BuildingRoomModuleHandler()
    embodied_handler = BuildingEmbodiedEnergyModuleHandler()
    session = _FakeSession()

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        bulk = AsyncMock(return_value={"BC01", "BC02"})
        mock_service_cls.return_value.get_room_names = bulk

        for handler in (rooms_handler, embodied_handler):
            for room_name in ("BC01", "BC02", "ZZ99"):
                await handler.enrich_csv_row({"room_name": room_name}, session)

    bulk.assert_awaited_once()


@pytest.mark.asyncio
async def test_fresh_session_does_not_reuse_a_previous_cache() -> None:
    """A new ingestion run (new session) reloads the ref data — a re-uploaded
    building rooms reference must be visible to the next CSV upload.
    """
    handler = BuildingRoomModuleHandler()

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        bulk = AsyncMock(return_value={"BC01"})
        mock_service_cls.return_value.get_room_names = bulk

        await handler.enrich_csv_row({"room_name": "BC01"}, _FakeSession())
        await handler.enrich_csv_row({"room_name": "BC01"}, _FakeSession())

    assert bulk.await_count == 2
