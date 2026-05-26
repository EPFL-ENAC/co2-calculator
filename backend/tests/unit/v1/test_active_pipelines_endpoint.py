"""#1234 — ``GET /sync/active-pipelines`` endpoint unit tests.

User-reported (2026-05-20) regression: the endpoint always returned
``{}`` for ``calco2.backoffice.metier`` users because of an over-eager
per-module OPA check (``modules.{name}.view``) that filtered out every
module the role doesn't have a per-module perm for.  But that role is
*global-scope by design* — it should see every module on the
data-management page.

The check was meant for a future sub-perimeter scoping (#459) but the
current OPA policy doesn't grant ``modules.X.view`` to BackOfficeMetier,
so the filter silently zero'd the response.  Removed: the global
``backoffice.data_management.view`` gate is sufficient until #459
ships a real sub-perimeter check.

These tests pin the endpoint to forward ``module_type_ids`` straight
through to the repo — no per-module pre-filter — so a future re-add of
the bug fails loudly.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import data_sync as data_sync_mod


@pytest.mark.asyncio
async def test_active_pipelines_forwards_modules_without_per_module_opa_filter():
    """Caller passes modules=[4] → endpoint forwards [4] to the repo
    method, no per-module OPA permission check in between.  This is
    the regression that broke BackOfficeMetier users on the
    data-management page (always {}).
    """
    fake_db = MagicMock()
    fake_user = MagicMock()
    fake_repo = MagicMock()
    fake_repo.get_current_pipeline_ids_for_modules = AsyncMock(
        return_value={4: "pipeline-uuid-stub"}
    )

    with patch.object(data_sync_mod, "DataIngestionRepository", return_value=fake_repo):
        result = await data_sync_mod.get_active_pipelines(
            year=2026,
            modules="4",
            db=fake_db,
            current_user=fake_user,
        )

    fake_repo.get_current_pipeline_ids_for_modules.assert_awaited_once_with(
        [4], year=2026
    )
    # Result is module_id → pipeline_id (string-serialised UUID).
    assert result == {4: "pipeline-uuid-stub"}


@pytest.mark.asyncio
async def test_active_pipelines_does_not_call_per_module_permission_check():
    """Pin the absence of the OPA call.  If a refactor reintroduces
    ``get_module_permission_decision`` in this endpoint without
    sub-perimeter scoping, it'll silently regress to filtering out
    every module for BackOfficeMetier — this test makes that loud."""
    fake_db = MagicMock()
    fake_user = MagicMock()
    fake_repo = MagicMock()
    fake_repo.get_current_pipeline_ids_for_modules = AsyncMock(return_value={})

    # Patch the policy function so any accidental invocation is visible.
    patched_decision = AsyncMock(return_value={"allow": True})
    with (
        patch.object(data_sync_mod, "DataIngestionRepository", return_value=fake_repo),
        patch("app.core.policy.get_module_permission_decision", patched_decision),
    ):
        await data_sync_mod.get_active_pipelines(
            year=2026,
            modules="4,5,6",
            db=fake_db,
            current_user=fake_user,
        )

    # Endpoint must NOT call the per-module permission helper.
    patched_decision.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_pipelines_empty_modules_short_circuits():
    """Empty ``modules`` query param returns ``{}`` without calling the
    repo — defensive contract, unchanged by the fix."""
    fake_db = MagicMock()
    fake_user = MagicMock()
    fake_repo = MagicMock()
    fake_repo.get_current_pipeline_ids_for_modules = AsyncMock()

    with patch.object(data_sync_mod, "DataIngestionRepository", return_value=fake_repo):
        result = await data_sync_mod.get_active_pipelines(
            year=2026, modules="", db=fake_db, current_user=fake_user
        )

    assert result == {}
    fake_repo.get_current_pipeline_ids_for_modules.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_pipelines_invalid_module_id_raises_400():
    """Non-integer module id → HTTP 400 (validation), unchanged by the fix."""
    from fastapi import HTTPException

    fake_db = MagicMock()
    fake_user = MagicMock()

    with pytest.raises(HTTPException) as exc:
        await data_sync_mod.get_active_pipelines(
            year=2026,
            modules="4,not-an-int",
            db=fake_db,
            current_user=fake_user,
        )
    assert exc.value.status_code == 400
