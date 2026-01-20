from unittest.mock import AsyncMock, patch

import pytest

from app.models.user import User
from app.services.data_ingestion.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
)


@pytest.mark.asyncio
async def test_professional_travel_fetch_data_mocked():
    config = {}
    user = User(id=1, username="your_tableau_username")

    provider = ProfessionalTravelApiProvider(config, user)
    filters = {}

    mock_result = {
        "data": [
            {
                "OUT_CO2_CORRECTED": 854.8,
                "OUT_DISTANCE_CORRECTED": 18754.0,
                "Centre financier": "F0555",
                "IN_Centre financier": "F0555",
                "IN_Departure date": "20250525",
                "IN_Segment class": "AIR ECONOMY CLASS",
                "IN_Segment destination": "LHR",
                "IN_Segment origin": "PVG",
                "IN_Segment destination airport code": "LHR",
                "IN_Segment origin airport code": "PVG",
                "IN_Supplier": "BRITISH AIRWAYS (BA)",
                "IN_Ticket number": "125 3574250902",
                "PASSENGER_TYPE": "",
                "ROUND_TRIP": "NO",
                "TRANSPORT_TYPE": "Plane",
                "Sciper": "385802",
                "Number of trips": 1,
            },
        ]
    }

    with patch.object(
        ProfessionalTravelApiProvider,
        "fetch_data",
        new=AsyncMock(return_value=mock_result),
    ):
        data = await provider.fetch_data(filters)
        assert data == mock_result
