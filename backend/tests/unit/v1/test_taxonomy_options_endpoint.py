"""#2391 decision 4 — ``GET /taxonomies/module/{module}/{data_entry}/options``.

The service logic is covered in ``tests/unit/services/
test_factor_option_search.py``; this file pins the route contract: path
validation shared with the taxonomy routes (404/400), the 400 for a data
entry type with nothing searchable, the FastAPI-level ``min_length``
rejection, and faithful delegation of every query param to the service.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1 import taxonomies as taxonomies_mod
from app.main import app
from app.models.data_entry import DataEntryTypeEnum
from app.schemas.taxonomy import FactorOption


@pytest.mark.asyncio
async def test_unknown_data_entry_404s():
    with pytest.raises(HTTPException) as exc:
        await taxonomies_mod.search_module_data_entry_options(
            module="purchase",
            data_entry="not-a-real-entry",
            query="outils",
            year=2025,
            lang="en",
            limit=20,
            db=object(),
            current_user=MagicMock(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_data_entry_of_other_module_400s():
    with pytest.raises(HTTPException) as exc:
        await taxonomies_mod.search_module_data_entry_options(
            module="purchase",
            data_entry="it",
            query="outils",
            year=2025,
            lang="en",
            limit=20,
            db=object(),
            current_user=MagicMock(),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_non_searchable_data_entry_400s():
    """Headcount handlers declare no kind field — nothing to search."""
    with pytest.raises(HTTPException) as exc:
        await taxonomies_mod.search_module_data_entry_options(
            module="headcount",
            data_entry="member",
            query="ab",
            year=2025,
            lang="en",
            limit=20,
            db=object(),
            current_user=MagicMock(),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delegates_every_param_to_the_service():
    captured: dict = {}

    async def fake_search(self, handler, det, year, query, lang, limit):
        captured.update(det=det, year=year, query=query, lang=lang, limit=limit)
        return [FactorOption(name="27112700", label="Outils électriques")]

    with patch.object(
        taxonomies_mod.ModuleHandlerService, "search_factor_options", new=fake_search
    ):
        result = await taxonomies_mod.search_module_data_entry_options(
            module="purchase",
            data_entry="other_purchases",
            query="outils",
            year=2026,
            lang="fr-CH",
            limit=30,
            db=object(),
            current_user=MagicMock(),
        )

    assert result == [FactorOption(name="27112700", label="Outils électriques")]
    assert captured == {
        "det": DataEntryTypeEnum.other_purchases,
        "year": 2026,
        "query": "outils",
        "lang": "fr-CH",
        "limit": 30,
    }


def test_query_below_min_length_422s():
    """FastAPI rejects a 1-char query before the handler runs — the same
    bound the frontend guard mirrors.
    """
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/taxonomies/module/purchase/other_purchases/options",
                params={"query": "a", "year": 2025},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
