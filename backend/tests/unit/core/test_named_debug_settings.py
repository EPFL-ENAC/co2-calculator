"""#3338: each former DEBUG effect follows its own named setting.

The route and middleware wiring happens at import time, so those checks
import the app in a subprocess with the setting in its environment (env
vars win over ``.env``, and the inherited pytest env keeps the in-memory DB).
"""

import os
import subprocess  # nosec B404
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import app.api.v1.auth as auth_module


def _run(code: str, **env: str) -> str:
    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", code],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


_LOGIN_TEST_REGISTERED = (
    "from app.api.v1.auth import oauth_router;"
    "print('/login-test' in {r.path for r in oauth_router.routes})"
)


@pytest.mark.parametrize("enabled", ["True", "False"])
def test_login_test_route_follows_its_flag(enabled):
    registered = _run(_LOGIN_TEST_REGISTERED, TEST_LOGIN_ROUTE_ENABLED=enabled)
    assert registered == enabled


_SESSION_HTTPS_ONLY = (
    "from starlette.middleware.sessions import SessionMiddleware;"
    "from app.main import app;"
    "print(next(m.kwargs['https_only'] for m in app.user_middleware"
    " if m.cls is SessionMiddleware))"
)


@pytest.mark.parametrize("secure", ["True", "False"])
def test_oauth_session_cookie_https_only_follows_cookie_secure(secure):
    assert _run(_SESSION_HTTPS_ONLY, COOKIE_SECURE=secure) == secure


async def _failed_callback_detail(monkeypatch, stack_trace: bool):
    monkeypatch.setattr(auth_module.settings, "DEBUG_STACK_TRACE_ENABLED", stack_trace)
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(side_effect=Exception("fail")),
    )
    with pytest.raises(HTTPException) as exc:
        await auth_module.oauth_callback(MagicMock(), MagicMock())
    return exc.value.detail


@pytest.mark.asyncio
async def test_failed_oauth_login_hides_traceback_by_default(monkeypatch):
    detail = await _failed_callback_detail(monkeypatch, stack_trace=False)
    assert detail == "Authentication failed"


@pytest.mark.asyncio
async def test_failed_oauth_login_returns_traceback_when_enabled(monkeypatch):
    detail = await _failed_callback_detail(monkeypatch, stack_trace=True)
    assert detail["error"] == "fail"
    assert any("Traceback" in line for line in detail["traceback"])
