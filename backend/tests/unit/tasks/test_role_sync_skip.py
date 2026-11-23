"""Regression: background role sync must not wipe roles for providers with
no out-of-band role source (#2295).

``JwtClaimsRoleProvider.get_user_by_user_id`` returns ``{}`` by design —
roles come from login-time JWT claims. Before ``supports_background_sync``,
``sync_user_roles`` read that empty dict as "user has zero roles now" and
silently erased ``roles_raw`` on the first TTL-expired session call, which
broke every database-seeded DEFAULT-provider user after one request.
"""

from contextlib import asynccontextmanager

import pytest

import app.tasks.role_sync_tasks as role_sync_tasks
from app.models.user import RoleName, User, UserProvider
from app.providers.role_provider import (
    AccredRoleProvider,
    JwtClaimsRoleProvider,
    TestRoleProvider,
)


def test_jwt_claims_provider_opts_out_of_background_sync():
    assert JwtClaimsRoleProvider.supports_background_sync is False
    assert AccredRoleProvider.supports_background_sync is True
    assert TestRoleProvider.supports_background_sync is True


@pytest.mark.asyncio
async def test_default_provider_user_roles_survive_background_sync(
    db_session, monkeypatch
):
    seeded_roles = [
        {
            "role": RoleName.CO2_USER_STD.value,
            "on": {"kind": "own", "institutional_id": "CF00042"},
        }
    ]
    user = User(
        id=1,
        institutional_id="USR000042",
        email="perf-user@example.org",
        provider=UserProvider.DEFAULT,
        roles_raw=seeded_roles,
        last_roles_sync_at=None,
    )
    db_session.add(user)
    await db_session.commit()

    @asynccontextmanager
    async def _session_ctx():
        yield db_session

    monkeypatch.setattr(role_sync_tasks, "SessionLocal", _session_ctx)

    await role_sync_tasks.trigger_role_sync_for_user(user.id, force=True)

    await db_session.refresh(user)
    assert user.roles_raw == seeded_roles


@pytest.mark.asyncio
async def test_background_sync_releases_connection_during_provider_call(
    db_session, monkeypatch
):
    """#2160: the task's own user lookup autobegins a transaction; it must
    be closed before the provider call, not held across it.
    """
    user = User(
        id=1,
        institutional_id="USR000042",
        email="perf-user@example.org",
        provider=UserProvider.ACCRED,
        roles_raw=[],
        last_roles_sync_at=None,
    )
    db_session.add(user)
    await db_session.commit()
    seen_in_transaction: list[bool] = []

    class _RecordingProvider:
        supports_background_sync = True

        async def get_user_by_user_id(self, _institutional_id: str) -> dict:
            seen_in_transaction.append(db_session.in_transaction())
            return {"roles": []}

    @asynccontextmanager
    async def _session_ctx():
        yield db_session

    monkeypatch.setattr(role_sync_tasks, "SessionLocal", _session_ctx)
    monkeypatch.setattr(
        role_sync_tasks, "get_role_provider", lambda _p: _RecordingProvider()
    )

    await role_sync_tasks.trigger_role_sync_for_user(user.id, force=True)

    assert seen_in_transaction == [False]
