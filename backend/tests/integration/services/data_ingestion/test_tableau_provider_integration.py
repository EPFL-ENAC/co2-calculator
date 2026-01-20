import pytest

from app.models.user import User
from app.services.data_ingestion.tableau_provider import TableauFlightsProvider

# @pytest.mark.asyncio
# async def test_tableau_ingest_real():
#     config = {}
#     user = User(id=1, username="your_tableau_username")  # Add other fields if needed

#     provider = TableauFlightsProvider(config, user)
#     filters = {
#         # Add any required filter keys here
#     }

#     try:
#         result = await provider.ingest(filters)
#         print("Ingest result:", result)
#         assert result["status_code"] == 200
#         assert "data" in result
#         assert "inserted" in result["data"]
#     except Exception as e:
#         print("Error during ingest:", e)
#         assert False, f"ingest failed: {e}"


@pytest.mark.asyncio
async def test_tableau_fetch_data_real():
    config = {}
    user = User(id=1, username="your_tableau_username")  # Add other fields if needed

    provider = TableauFlightsProvider(config, user)
    filters = {
        # Add any required filter keys here, e.g.:
        # "year": 2025,
        # "some_meta": "value",
    }

    try:
        data = await provider.fetch_data(filters)
        print("Fetched data:", data)
        # assert isinstance(data, list)
        # Optionally, check for at least one record or required keys
        # if data:
        #     assert "sciper" in data[0] or "Sciper" in data[0]
    except Exception as e:
        print("Error during fetch_data:", e)
        assert False, f"fetch_data failed: {e}"
