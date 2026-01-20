import pytest

from app.models.user import User
from app.services.data_ingestion.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
)


@pytest.mark.asyncio
async def test_professional_travel_fetch_data_real():
    config = {}
    user = User(id=1, username="your_tableau_username")  # Add other fields if needed

    provider = ProfessionalTravelApiProvider(config, user)
    filters = {
        # Add any required filter keys here, e.g.:
        # "year": 2025,
        # "some_meta": "value",
    }

    try:
        data = await provider.fetch_data(filters)
        print("Fetched data:", data)
    except Exception as e:
        print("Error during fetch_data:", e)
        assert False, f"fetch_data failed: {e}"
