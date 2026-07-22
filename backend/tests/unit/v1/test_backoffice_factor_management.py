"""Tests for the backoffice factor viewer and bulk delete endpoints (#1491).

The recalc fan-out is asserted through the mocked
``DataIngestionRepository`` / ``fire_and_forget`` pair — same approach the
sync endpoint tests use: the job row's shape is the contract, the runner
is out of scope here.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.core.security as security_module
from app.api.deps import get_db
from app.main import app

BASE = "/api/v1/backoffice"


@pytest.fixture
def client(monkeypatch):
    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"
    fake_user.provider = 0

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(security_module, "is_permitted", _allow)

    db = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )
    with TestClient(app) as c:
        c.db = db  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


def _mock_ingestion_repo():
    """DataIngestionRepository mock capturing the dispatched recalc job."""
    repo = MagicMock()
    repo.ensure_pipeline_exists = AsyncMock()
    repo.create_ingestion_job = AsyncMock(
        side_effect=lambda job: SimpleNamespace(**{**job.__dict__, "id": 77})
    )
    return repo


# ---------------------------------------------------------------------------
# GET /backoffice/factors
# ---------------------------------------------------------------------------


def test_list_factors_paginated_with_last_seen_job_id(client):
    factor = MagicMock()
    factor.year = 2024
    factor.last_seen_job_id = 42

    factor_repo = MagicMock()
    factor_repo.count_by_data_entry_type_and_year = AsyncMock(return_value=3)
    factor_repo.list_by_data_entry_type = AsyncMock(return_value=[factor, factor])

    handler = MagicMock()
    handler.to_response.return_value = SimpleNamespace(
        model_dump=lambda: {"id": 5, "kind": "plane", "co2": 1.5}
    )

    with (
        patch("app.api.v1.backoffice.FactorRepository", return_value=factor_repo),
        patch(
            "app.api.v1.backoffice.BaseFactorHandler.get_by_type",
            return_value=handler,
        ),
    ):
        resp = client.get(
            f"{BASE}/factors",
            params={
                "data_entry_type_id": 1,
                "year": 2024,
                "page": 1,
                "page_size": 2,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "total_pages": 2,
    }
    assert body["data"][0]["kind"] == "plane"
    assert body["data"][0]["last_seen_job_id"] == 42
    assert body["data"][0]["year"] == 2024
    factor_repo.list_by_data_entry_type.assert_awaited_once()
    _, kwargs = factor_repo.list_by_data_entry_type.await_args
    assert kwargs == {"limit": 2, "offset": 0}


def test_list_factors_unknown_data_entry_type_400(client):
    resp = client.get(
        f"{BASE}/factors",
        params={"data_entry_type_id": 999999, "year": 2024},
    )
    assert resp.status_code == 400
    assert "data_entry_type_id" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /backoffice/factors
# ---------------------------------------------------------------------------


def test_delete_factors_dispatches_emission_recalc(client):
    factor_repo = MagicMock()
    factor_repo.list_id_by_data_entry_type_and_year = AsyncMock(return_value=[1, 2, 3])
    factor_repo.bulk_delete = AsyncMock()

    ingestion_repo = _mock_ingestion_repo()
    fired = MagicMock()

    with (
        patch("app.api.v1.backoffice.FactorRepository", return_value=factor_repo),
        patch(
            "app.api.v1.backoffice.DataIngestionRepository",
            return_value=ingestion_repo,
        ),
        patch("app.api.v1.backoffice.fire_and_forget", fired),
        patch("app.api.v1.backoffice.run_job", MagicMock()),
    ):
        resp = client.delete(
            f"{BASE}/factors",
            params={"data_entry_type_id": 1, "year": 2024},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 3
    assert body["recalc_job_id"] == 77
    assert body["recalc_pipeline_id"]
    factor_repo.bulk_delete.assert_awaited_once_with([1, 2, 3])

    # The chained recalc job targets the deleted scope.
    job = ingestion_repo.create_ingestion_job.await_args.args[0]
    assert job.job_type == "emission_recalc"
    assert job.data_entry_type_id == 1
    assert job.year == 2024
    assert job.module_type_id is not None
    assert "carbon_report_module_ids" not in job.meta["config"]
    fired.assert_called_once()


def test_delete_factors_empty_scope_skips_recalc(client):
    factor_repo = MagicMock()
    factor_repo.list_id_by_data_entry_type_and_year = AsyncMock(return_value=[])
    factor_repo.bulk_delete = AsyncMock()

    fired = MagicMock()
    with (
        patch("app.api.v1.backoffice.FactorRepository", return_value=factor_repo),
        patch("app.api.v1.backoffice.fire_and_forget", fired),
    ):
        resp = client.delete(
            f"{BASE}/factors",
            params={"data_entry_type_id": 1, "year": 2024},
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "deleted": 0,
        "recalc_job_id": None,
        "recalc_pipeline_id": None,
    }
    factor_repo.bulk_delete.assert_not_awaited()
    fired.assert_not_called()


# ---------------------------------------------------------------------------
# DELETE /backoffice/data-entries
# ---------------------------------------------------------------------------


def test_delete_data_entries_year_scoped_dispatches_recalc(client):
    service = MagicMock()
    service.repo.bulk_delete_by_source_year = AsyncMock(return_value=5)

    ingestion_repo = _mock_ingestion_repo()
    fired = MagicMock()

    with (
        patch("app.api.v1.backoffice.DataEntryService", return_value=service),
        patch(
            "app.api.v1.backoffice.DataIngestionRepository",
            return_value=ingestion_repo,
        ),
        patch("app.api.v1.backoffice.fire_and_forget", fired),
        patch("app.api.v1.backoffice.run_job", MagicMock()),
    ):
        resp = client.delete(
            f"{BASE}/data-entries",
            params={"data_entry_type_id": 1, "source": 1, "year": 2024},
        )

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 5
    service.repo.bulk_delete_by_source_year.assert_awaited_once_with(2024, [1], 1)

    job = ingestion_repo.create_ingestion_job.await_args.args[0]
    assert job.job_type == "emission_recalc"
    assert job.data_entry_type_id == 1
    assert job.year == 2024
    # Year-scoped delete → unscoped (full-slice) recalc.
    assert "carbon_report_module_ids" not in job.meta["config"]
    fired.assert_called_once()


def test_delete_data_entries_module_scoped_pins_recalc_to_module(client):
    module_year_result = MagicMock()
    module_year_result.scalar_one_or_none.return_value = 2024
    count_result = MagicMock()
    count_result.scalar_one.return_value = 4
    client.db.execute = AsyncMock(side_effect=[module_year_result, count_result])

    service = MagicMock()
    service.bulk_delete_by_source = AsyncMock()

    ingestion_repo = _mock_ingestion_repo()
    fired = MagicMock()

    with (
        patch("app.api.v1.backoffice.DataEntryService", return_value=service),
        patch(
            "app.api.v1.backoffice.DataIngestionRepository",
            return_value=ingestion_repo,
        ),
        patch("app.api.v1.backoffice.UserRead") as user_read,
        patch("app.api.v1.backoffice.fire_and_forget", fired),
        patch("app.api.v1.backoffice.run_job", MagicMock()),
    ):
        resp = client.delete(
            f"{BASE}/data-entries",
            params={
                "data_entry_type_id": 1,
                "source": 1,
                "year": 2024,
                "carbon_report_module_id": 10,
            },
        )

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 4
    service.bulk_delete_by_source.assert_awaited_once()
    args, kwargs = service.bulk_delete_by_source.await_args
    assert args[0] == 10  # carbon_report_module_id
    assert kwargs["user"] is user_read.model_validate.return_value

    # Module-scoped delete → module-scoped recalc.
    job = ingestion_repo.create_ingestion_job.await_args.args[0]
    assert job.meta["config"]["carbon_report_module_ids"] == [10]
    fired.assert_called_once()


def test_delete_data_entries_module_year_mismatch_400(client):
    module_year_result = MagicMock()
    module_year_result.scalar_one_or_none.return_value = 2023
    client.db.execute = AsyncMock(return_value=module_year_result)

    service = MagicMock()
    service.bulk_delete_by_source = AsyncMock()
    fired = MagicMock()

    with (
        patch("app.api.v1.backoffice.DataEntryService", return_value=service),
        patch("app.api.v1.backoffice.fire_and_forget", fired),
    ):
        resp = client.delete(
            f"{BASE}/data-entries",
            params={
                "data_entry_type_id": 1,
                "source": 1,
                "year": 2024,
                "carbon_report_module_id": 10,
            },
        )

    assert resp.status_code == 400
    assert "2023" in resp.json()["detail"]
    service.bulk_delete_by_source.assert_not_awaited()
    fired.assert_not_called()


def test_delete_data_entries_unknown_source_400(client):
    resp = client.delete(
        f"{BASE}/data-entries",
        params={"data_entry_type_id": 1, "source": 999, "year": 2024},
    )
    assert resp.status_code == 400
    assert "source" in resp.json()["detail"].lower()


def test_delete_data_entries_nothing_deleted_skips_recalc(client):
    service = MagicMock()
    service.repo.bulk_delete_by_source_year = AsyncMock(return_value=0)
    fired = MagicMock()

    with (
        patch("app.api.v1.backoffice.DataEntryService", return_value=service),
        patch("app.api.v1.backoffice.fire_and_forget", fired),
    ):
        resp = client.delete(
            f"{BASE}/data-entries",
            params={"data_entry_type_id": 1, "source": 1, "year": 2024},
        )

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0
    fired.assert_not_called()
