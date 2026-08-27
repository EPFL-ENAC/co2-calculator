"""Regression test: plane's unknown-IATA path must fail hard, not silently.

Companion to #1186 (train natural_key validation) — the same silent
zero-emission shape existed on the plane side: an IATA code that doesn't
resolve to a ``Location`` row used to log a WARNING and return ``{}`` from
``pre_compute``, leaving the entry persisted with zero emissions and no
visible error. ``pre_compute``'s raised ``ValueError`` is already handled
correctly by both call paths (see #2050 J1): a 422 on synchronous create/
update (``CarbonReportModuleWorkflow``'s ``except ValueError``), and a
per-entry-isolated error during batch recalc (``EmissionRecalculationWorkflow``'s
``except Exception`` loop, which does not abort the rest of the slice).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.professional_travel import ProfessionalTravelPlaneModuleHandler


def _entry(origin_iata: str, destination_iata: str) -> MagicMock:
    entry = MagicMock()
    entry.id = 1
    entry.data = {
        "origin_iata": origin_iata,
        "destination_iata": destination_iata,
        "number_of_trips": 1,
    }
    return entry


@pytest.mark.asyncio
async def test_plane_pre_compute_raises_on_unknown_destination_iata():
    handler = ProfessionalTravelPlaneModuleHandler()

    with patch(
        "app.modules.professional_travel.handlers.LocationService"
    ) as mock_service_cls:
        origin = MagicMock()
        mock_service_cls.return_value.get_location_by_iata = AsyncMock(
            side_effect=[origin, None]
        )

        with pytest.raises(ValueError, match="XXX"):
            await handler.pre_compute(_entry("GVA", "XXX"), MagicMock())
