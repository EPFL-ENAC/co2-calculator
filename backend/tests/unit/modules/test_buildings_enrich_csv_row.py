"""Buildings CSV rows are checked against the room reference, in bulk
(#2253, #2716, #2268).

``enrich_csv_row`` runs once per CSV row; the original check did one
``building_rooms`` SELECT per row. The known-room index now loads once per
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


def _patched_rooms(rows: list[tuple[str, float | None]]):
    patcher = patch("app.modules.buildings.handlers.BuildingRoomService")
    mock_service_cls = patcher.start()
    bulk = AsyncMock(return_value=rows)
    mock_service_cls.return_value.get_room_surfaces = bulk
    return patcher, bulk


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

    patcher, _ = _patched_rooms([("BC01", 18.0)])
    try:
        enriched, err = await handler.enrich_csv_row(data, _FakeSession())
    finally:
        patcher.stop()

    assert err is not None
    assert "ZZ99" in err
    assert "not found in the building rooms reference" in err
    assert enriched == data


@pytest.mark.asyncio
async def test_known_room_passes_with_data_unchanged() -> None:
    handler = BuildingRoomModuleHandler()
    data = {"building_name": "BC", "room_name": "BC01"}

    patcher, _ = _patched_rooms([("BC01", 18.0)])
    try:
        enriched, err = await handler.enrich_csv_row(data, _FakeSession())
    finally:
        patcher.stop()

    assert err is None
    assert enriched == data


@pytest.mark.asyncio
async def test_room_without_surface_is_a_hard_row_error() -> None:
    """The room exists in the reference but its surface cell is empty: the
    entry would compute to nothing, silently — the #2716 gap.
    """
    handler = BuildingRoomModuleHandler()
    data = {"building_name": "AI", "room_name": "AI 2 46.1"}

    patcher, _ = _patched_rooms([("AI 2 46.1", None)])
    try:
        enriched, err = await handler.enrich_csv_row(data, _FakeSession())
    finally:
        patcher.stop()

    assert err is not None
    assert "AI 2 46.1" in err
    assert "no surface" in err
    assert enriched == data


@pytest.mark.asyncio
async def test_zero_surface_room_passes() -> None:
    """The schema permits 0: the guard is on None, not falsiness."""
    handler = BuildingRoomModuleHandler()
    data = {"building_name": "BC", "room_name": "BC01"}

    patcher, _ = _patched_rooms([("BC01", 0.0)])
    try:
        _, err = await handler.enrich_csv_row(data, _FakeSession())
    finally:
        patcher.stop()

    assert err is None


@pytest.mark.asyncio
async def test_room_name_matches_with_spaces_ignored_and_is_canonicalised() -> None:
    """#2268: ``AI 9121`` on the upload is the reference's ``AI 9 121``; the
    persisted row carries the reference spelling so compute-time lookups
    stay exact.
    """
    handler = BuildingRoomModuleHandler()

    patcher, _ = _patched_rooms([("AI 9 121", 12.5)])
    try:
        enriched, err = await handler.enrich_csv_row(
            {"building_name": "AI", "room_name": "AI 9121"}, _FakeSession()
        )
        (
            embodied,
            embodied_err,
        ) = await BuildingEmbodiedEnergyModuleHandler().enrich_csv_row(
            {"room_name": "AI9121"}, _FakeSession()
        )
    finally:
        patcher.stop()

    assert err is None
    assert enriched == {"building_name": "AI", "room_name": "AI 9 121"}
    assert embodied_err is None
    assert embodied == {"room_name": "AI 9 121"}


@pytest.mark.asyncio
async def test_many_rows_and_both_handlers_share_one_query_per_session() -> None:
    """The point of the batching: N rows → a single room-surfaces query."""
    rooms_handler = BuildingRoomModuleHandler()
    embodied_handler = BuildingEmbodiedEnergyModuleHandler()
    session = _FakeSession()

    patcher, bulk = _patched_rooms([("BC01", 1.0), ("BC02", 2.0)])
    try:
        for handler in (rooms_handler, embodied_handler):
            for room_name in ("BC01", "BC02", "ZZ99"):
                await handler.enrich_csv_row({"room_name": room_name}, session)
    finally:
        patcher.stop()

    bulk.assert_awaited_once()


@pytest.mark.asyncio
async def test_fresh_session_does_not_reuse_a_previous_cache() -> None:
    """A new ingestion run (new session) reloads the ref data — a re-uploaded
    building rooms reference must be visible to the next CSV upload.
    """
    handler = BuildingRoomModuleHandler()

    patcher, bulk = _patched_rooms([("BC01", 1.0)])
    try:
        await handler.enrich_csv_row({"room_name": "BC01"}, _FakeSession())
        await handler.enrich_csv_row({"room_name": "BC01"}, _FakeSession())
    finally:
        patcher.stop()

    assert bulk.await_count == 2
