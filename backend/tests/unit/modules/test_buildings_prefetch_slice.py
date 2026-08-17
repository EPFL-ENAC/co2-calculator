"""Buildings room lookups batch per slice instead of per entry (plan #2050).

``pre_compute`` needs every entry's room surface. Without a
``prefetch_slice``, that is one ``building_rooms`` round trip per entry —
measured at 364 selects on a single 11-year plan-range PATCH.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.buildings.handlers import BuildingRoomModuleHandler


def _entry(room_name: str | None, building_name: str = "BC") -> MagicMock:
    entry = MagicMock()
    entry.id = 1
    entry.data = {"room_name": room_name, "building_name": building_name}
    return entry


def _room(room_name: str, surface: float) -> MagicMock:
    room = MagicMock()
    room.room_name = room_name
    room.room_surface_square_meter = surface
    return room


@pytest.mark.asyncio
async def test_prefetch_slice_loads_every_room_in_one_query():
    """N entries → a single bulk lookup, deduped, keyed by room name."""
    handler = BuildingRoomModuleHandler()
    entries = [_entry("BC01"), _entry("BC02"), _entry("BC01"), _entry(None)]

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        mock_service_cls.return_value.get_rooms_by_names = AsyncMock(
            return_value=[_room("BC01", 10.0), _room("BC02", 20.0)]
        )
        cache = await handler.prefetch_slice(entries, MagicMock(), year=2026)
        bulk = mock_service_cls.return_value.get_rooms_by_names

    bulk.assert_awaited_once_with(["BC01", "BC02"])
    assert set(cache["rooms"]) == {"BC01", "BC02"}


@pytest.mark.asyncio
async def test_pre_compute_reads_the_slice_cache_without_touching_the_db():
    """The whole point: a cached slice means zero per-entry round trips."""
    handler = BuildingRoomModuleHandler()
    cache = {"rooms": {"BC01": _room("BC01", 42.0)}}

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        mock_service_cls.return_value.get_room = AsyncMock()
        ctx = await handler.pre_compute(_entry("BC01"), MagicMock(), slice_cache=cache)
        mock_service_cls.return_value.get_room.assert_not_awaited()

    assert ctx == {"room_surface_square_meter": 42.0}


@pytest.mark.asyncio
async def test_pre_compute_without_slice_cache_still_queries_per_entry():
    """Single-entry create/update has no slice — the fallback must stay."""
    handler = BuildingRoomModuleHandler()

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        mock_service_cls.return_value.get_room = AsyncMock(
            return_value=_room("BC01", 7.0)
        )
        ctx = await handler.pre_compute(_entry("BC01"), MagicMock())
        mock_service_cls.return_value.get_room.assert_awaited_once_with(
            room_name="BC01"
        )

    assert ctx == {"room_surface_square_meter": 7.0}


@pytest.mark.asyncio
async def test_prefetch_slice_without_room_names_stays_empty():
    """No rooms to load → no query, and pre_compute keeps its fallback."""
    handler = BuildingRoomModuleHandler()

    with patch(
        "app.modules.buildings.handlers.BuildingRoomService"
    ) as mock_service_cls:
        mock_service_cls.return_value.get_rooms_by_names = AsyncMock()
        cache = await handler.prefetch_slice([_entry(None)], MagicMock())
        mock_service_cls.return_value.get_rooms_by_names.assert_not_awaited()

    assert cache == {}
