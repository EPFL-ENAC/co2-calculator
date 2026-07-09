import pytest

from app.models.connector import ConnectorConnection, ConnectorType
from app.repositories.connector_repo import ConnectorConnectionRepository


@pytest.mark.asyncio
async def test_get_by_connector_returns_saved_connection(db_session):
    repo = ConnectorConnectionRepository(db_session)
    saved = await repo.upsert(
        ConnectorConnection(
            connector=ConnectorType.EPFL_TABLEAU,
            label="EPFL Tableau",
            server_url="https://tableau.epfl.ch/",
            site_content_url="co2fp",
            username="svc-calcco2-epfl-api",
            client_id="cid",
            secret_id="sid",
            secret_value_encrypted="enc",
        )
    )
    await db_session.commit()
    found = await repo.get_by_connector(ConnectorType.EPFL_TABLEAU)
    assert found is not None
    assert found.id == saved.id
    assert found.server_url == "https://tableau.epfl.ch/"
