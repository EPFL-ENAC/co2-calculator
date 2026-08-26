"""#2049 T6 -- batched ``GET /taxonomies/module/{module}/data-entries``.

A report page fires ~11 sequential ``GET /taxonomies/module/{module}/
{data_entry}`` calls per load (docs/src/implementation-plans/
2049-optimize-pipeline-performance.md, S1.5/S3.4). This endpoint collapses
one module's data entries into a single round trip. It must return exactly
what N calls to the single-entry endpoint would -- same data, keyed by the
requested entry name -- and still fail loudly on an unresolvable entry
instead of silently dropping it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1 import taxonomies as taxonomies_mod
from app.main import app
from app.schemas.taxonomy import TaxonomyNode


def _fake_taxonomy(data_entry_type) -> TaxonomyNode:
    return TaxonomyNode(name=data_entry_type.name, label=data_entry_type.name)


@pytest.mark.asyncio
async def test_batch_endpoint_matches_n_single_entry_calls():
    """Batched result == calling the single-entry endpoint once per entry."""
    fake_db = object()
    fake_user = object()

    with patch.object(
        taxonomies_mod.ModuleHandlerService,
        "get_taxonomy",
        new=AsyncMock(
            side_effect=lambda handler, data_entry_type, year: _fake_taxonomy(
                data_entry_type
            )
        ),
    ):
        batched = await taxonomies_mod.get_taxonomies_for_module_data_entries(
            response=Response(),
            module="equipment",
            entries=["scientific", "it"],
            year=2025,
            db=fake_db,
            current_user=fake_user,
        )

        single_scientific = await taxonomies_mod.get_taxonomy_for_module_data_entry(
            response=Response(),
            module="equipment",
            data_entry="scientific",
            year=2025,
            db=fake_db,
            current_user=fake_user,
        )
        single_it = await taxonomies_mod.get_taxonomy_for_module_data_entry(
            response=Response(),
            module="equipment",
            data_entry="it",
            year=2025,
            db=fake_db,
            current_user=fake_user,
        )

    assert batched == {"scientific": single_scientific, "it": single_it}
    # Insertion order mirrors the requested `entries` order (no reordering).
    assert list(batched.keys()) == ["scientific", "it"]


@pytest.mark.asyncio
async def test_batch_endpoint_unknown_entry_raises_404_not_skipped():
    """An unresolvable entry must fail loudly, not be silently dropped."""
    fake_db = object()
    fake_user = object()

    with patch.object(
        taxonomies_mod.ModuleHandlerService,
        "get_taxonomy",
        new=AsyncMock(
            side_effect=lambda handler, data_entry_type, year: _fake_taxonomy(
                data_entry_type
            )
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await taxonomies_mod.get_taxonomies_for_module_data_entries(
                response=Response(),
                module="equipment",
                entries=["scientific", "not-a-real-entry"],
                year=2025,
                db=fake_db,
                current_user=fake_user,
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_batch_endpoint_entry_from_other_module_raises_400():
    """An entry that belongs to a different module must 400, not be dropped."""
    fake_db = object()
    fake_user = object()

    with patch.object(
        taxonomies_mod.ModuleHandlerService,
        "get_taxonomy",
        new=AsyncMock(
            side_effect=lambda handler, data_entry_type, year: _fake_taxonomy(
                data_entry_type
            )
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await taxonomies_mod.get_taxonomies_for_module_data_entries(
                response=Response(),
                module="equipment",
                entries=["scientific", "building"],  # building belongs to buildings
                year=2025,
                db=fake_db,
                current_user=fake_user,
            )
    assert exc.value.status_code == 400


def test_batch_route_wins_over_single_entry_catch_all():
    """Starlette matches routes in registration order: '/data-entries' must
    resolve to the batch handler, not be swallowed as a {data_entry} value
    by the single-entry route registered after it.
    """
    fake_user = MagicMock()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: fake_user

    try:
        with patch.object(
            taxonomies_mod.ModuleHandlerService,
            "get_taxonomy",
            new=AsyncMock(
                side_effect=lambda handler, data_entry_type, year: _fake_taxonomy(
                    data_entry_type
                )
            ),
        ):
            with TestClient(app) as client:
                response = client.get(
                    "/api/v1/taxonomies/module/equipment/data-entries",
                    params={"entries": ["scientific", "it"], "year": 2025},
                )
    finally:
        app.dependency_overrides.clear()

    # The single-entry route would 404 ("Data entry type not found") since
    # "data-entries" is not a DataEntryTypeEnum member -- 200 here proves
    # the batch route matched instead.
    assert response.status_code == 200
    assert set(response.json().keys()) == {"scientific", "it"}


@pytest.mark.asyncio
async def test_batch_endpoint_isolates_a_per_entry_runtime_failure():
    """#2258 follow-up: a per-entry runtime failure (not a request-shape
    bug like an unknown/mismatched entry — see the 404/400 tests above)
    must not blank every other, already-resolved entry in the batch.
    """
    fake_db = object()
    fake_user = object()

    async def _flaky_get_taxonomy(handler, data_entry_type, year):
        if data_entry_type.name == "it":
            raise RuntimeError("transient DB hiccup")
        return _fake_taxonomy(data_entry_type)

    with patch.object(
        taxonomies_mod.ModuleHandlerService,
        "get_taxonomy",
        new=AsyncMock(side_effect=_flaky_get_taxonomy),
    ):
        batched = await taxonomies_mod.get_taxonomies_for_module_data_entries(
            response=Response(),
            module="equipment",
            entries=["scientific", "it", "other"],
            year=2025,
            db=fake_db,
            current_user=fake_user,
        )

    assert set(batched.keys()) == {"scientific", "other"}


@pytest.mark.asyncio
async def test_batch_endpoint_still_sets_the_cache_header():
    """The batch route must carry the same ``Cache-Control`` as the
    single-entry one.

    #2258 (server cache + browser caching) and #2049 T6 (batching) landed
    together and meet exactly here: batching introduced a shared resolver,
    and it would have been easy to thread the response through the
    single-entry route only. Then the endpoint the frontend actually calls
    would silently lose its cache header while every other test still
    passed.
    """
    with patch.object(
        taxonomies_mod.ModuleHandlerService,
        "get_taxonomy",
        new=AsyncMock(
            side_effect=lambda handler, data_entry_type, year: _fake_taxonomy(
                data_entry_type
            )
        ),
    ):
        response = Response()
        await taxonomies_mod.get_taxonomies_for_module_data_entries(
            response=response,
            module="equipment",
            entries=["scientific", "it"],
            year=2025,
            db=object(),
            current_user=object(),
        )

    assert response.headers["Cache-Control"] == taxonomies_mod._CACHE_CONTROL
