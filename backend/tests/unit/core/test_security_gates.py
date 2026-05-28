"""Regression tests for the authorization gates in `app.core.security`.

Covers issue #458's "Unauthorized access attempts" success criterion at the
gate level — the per-endpoint integration is exercised by
`tests/integration/v1/test_permission_scope_e2e.py`. These tests pin:

- `is_permitted` honours an OPA deny / allow decision
- `check_permission` raises 403 on deny, returns on allow
- `require_permission` (the FastAPI dependency factory) raises 403
- Glob expansion in `is_permitted` denies if ANY matching path is denied
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.security import (
    check_permission,
    is_permitted,
    require_permission,
)


def _user_with_paths(paths: list[str]) -> MagicMock:
    """Build a mock User whose calculate_permissions returns the given paths."""
    user = MagicMock()
    user.id = 42
    user.email = "user@example.org"
    user.roles = []
    user.calculate_permissions.return_value = {p: ["view"] for p in paths}
    return user


@pytest.mark.asyncio
async def test_is_permitted_denies_when_opa_denies(monkeypatch):
    monkeypatch.setattr(
        "app.core.security.query_policy",
        AsyncMock(return_value={"allow": False, "reason": "no role"}),
    )
    user = _user_with_paths(["modules.headcount"])
    assert await is_permitted(user, "modules.headcount", "view") is False


@pytest.mark.asyncio
async def test_is_permitted_allows_when_opa_allows(monkeypatch):
    monkeypatch.setattr(
        "app.core.security.query_policy",
        AsyncMock(return_value={"allow": True}),
    )
    user = _user_with_paths(["modules.headcount"])
    assert await is_permitted(user, "modules.headcount", "view") is True


@pytest.mark.asyncio
async def test_check_permission_raises_403_when_denied(monkeypatch):
    monkeypatch.setattr(
        "app.core.security.query_policy",
        AsyncMock(return_value={"allow": False}),
    )
    user = _user_with_paths(["modules.headcount"])
    with pytest.raises(HTTPException) as exc:
        await check_permission(user, "modules.headcount", "view")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_check_permission_returns_none_when_allowed(monkeypatch):
    monkeypatch.setattr(
        "app.core.security.query_policy",
        AsyncMock(return_value={"allow": True}),
    )
    user = _user_with_paths(["modules.headcount"])
    assert await check_permission(user, "modules.headcount", "view") is None


@pytest.mark.asyncio
async def test_require_permission_dependency_raises_403_when_denied(monkeypatch):
    """The FastAPI dependency built by `require_permission` must surface a
    403 (not 401) when the user is authenticated but not authorized."""
    monkeypatch.setattr(
        "app.core.security.query_policy",
        AsyncMock(return_value={"allow": False}),
    )
    user = _user_with_paths(["modules.headcount"])
    dep = require_permission("modules.headcount", "view")
    with pytest.raises(HTTPException) as exc:
        await dep(user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_permission_dependency_returns_user_when_allowed(monkeypatch):
    monkeypatch.setattr(
        "app.core.security.query_policy",
        AsyncMock(return_value={"allow": True}),
    )
    user = _user_with_paths(["modules.headcount"])
    dep = require_permission("modules.headcount", "view")
    result = await dep(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_is_permitted_glob_denies_if_any_match_denied(monkeypatch):
    """Pin the AND-semantics of glob expansion in `is_permitted`: a `modules.*`
    check must DENY if even one matching path is denied. A relaxation here
    would silently grant cross-module access."""
    user = _user_with_paths(["modules.headcount", "modules.travel", "modules.purchase"])

    async def policy(path: str, input_data: dict):
        # Deny only `modules.travel`
        if input_data["path"] == "modules.travel":
            return {"allow": False}
        return {"allow": True}

    monkeypatch.setattr("app.core.security.query_policy", policy)
    assert await is_permitted(user, "modules.*", "view") is False


@pytest.mark.asyncio
async def test_is_permitted_no_glob_match_falls_through_to_opa(monkeypatch):
    """When the requested path matches no known user-permission keys, the
    glob short-circuit must not silently return True — defer to OPA."""
    user = _user_with_paths(["modules.headcount"])
    opa = AsyncMock(return_value={"allow": False})
    monkeypatch.setattr("app.core.security.query_policy", opa)

    assert await is_permitted(user, "system.config", "view") is False
    opa.assert_awaited()  # OPA must have been consulted
