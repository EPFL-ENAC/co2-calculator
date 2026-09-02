"""Integration tests for ``POST /api/v1/users/{user_id}/revoke-roles`` (#2539).

Mocks ``is_permitted`` (matching ``test_year_configuration_init.py``'s
convention) since this only needs an admin/non-admin toggle to reach the
revoke logic — the real permission chain is covered elsewhere
(``test_permission_scope_e2e.py``).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.main import app
from app.models.user import Role, User, UserProvider
from tests.browser import SAME_ORIGIN_HEADERS
from tests.unit.v1.test_temp_upload_auth_ordering import valid_access_token

REVOKE_URL = "/api/v1/users/{user_id}/revoke-roles"


@pytest_asyncio.fixture
async def db_factory():
    """In-memory SQLite with all tables created, no seeded rows."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def client():
    # AuthFirstRoute (#2261) verifies the JWT cookie before dependencies
    # run, so the get_current_user override alone doesn't get past it.
    with TestClient(
        app,
        cookies={"auth_token": valid_access_token()},
        headers=SAME_ORIGIN_HEADERS,
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _admin() -> MagicMock:
    u = MagicMock()
    u.id = 99
    u.email = "admin@example.com"
    u.institutional_id = "99999"
    u.provider = UserProvider.DEFAULT
    return u


async def _seed_target(factory, *, roles_raw, provider=UserProvider.ACCRED) -> int:
    async with factory() as session:
        target = User(
            institutional_id="11111",
            email="target@example.com",
            provider=provider,
            roles_raw=roles_raw,
        )
        session.add(target)
        await session.commit()
        await session.refresh(target)
        return target.id


def _wire(monkeypatch, factory, *, is_admin: bool) -> None:
    app.dependency_overrides[deps_module.get_current_user] = _admin

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db

    async def fake_is_permitted(user, path, action="view"):
        if path == "backoffice.users" and action == "edit":
            return is_admin
        return False

    monkeypatch.setattr("app.core.security.is_permitted", fake_is_permitted)


def _mock_accred_returning(monkeypatch, roles_raw: list[dict]):
    """Stub the role provider factory so no real Accred call happens."""
    provider = AsyncMock()
    provider.supports_background_sync = True
    provider.get_user_by_user_id = AsyncMock(
        return_value={"roles": [Role(**r) for r in roles_raw]}
    )
    monkeypatch.setattr(
        "app.api.v1.users.get_role_provider", lambda *_args, **_kw: provider
    )
    return provider


ROLE_RAW = {
    "role": "calco2.user.standard",
    "on": {"kind": "own", "institutional_id": "unit1"},
}


class TestRevokeRolesPermissionGate:
    @pytest.mark.asyncio
    async def test_non_admin_forbidden(self, client, monkeypatch, db_factory):
        _wire(monkeypatch, db_factory, is_admin=False)
        user_id = await _seed_target(db_factory, roles_raw=[ROLE_RAW])
        _mock_accred_returning(monkeypatch, [])

        r = client.post(REVOKE_URL.format(user_id=user_id))

        assert r.status_code == 403, r.text

    @pytest.mark.asyncio
    async def test_unknown_user_404s(self, client, monkeypatch, db_factory):
        _wire(monkeypatch, db_factory, is_admin=True)
        _mock_accred_returning(monkeypatch, [])

        r = client.post(REVOKE_URL.format(user_id=999999))

        assert r.status_code == 404, r.text


class TestRevokeRolesForcesTheGuard:
    @pytest.mark.asyncio
    async def test_admin_revoke_applies_even_though_provider_returns_empty(
        self, client, monkeypatch, db_factory
    ):
        """The whole point of #2539's admin path: a human confirmed intent,
        so a single fresh empty check applies immediately — no two-strikes
        wait, unlike the automatic /v1/session path.
        """
        _wire(monkeypatch, db_factory, is_admin=True)
        user_id = await _seed_target(db_factory, roles_raw=[ROLE_RAW])
        _mock_accred_returning(monkeypatch, [])

        r = client.post(REVOKE_URL.format(user_id=user_id))

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["outcome"] == "applied"
        assert body["new_roles"] == []

    @pytest.mark.asyncio
    async def test_admin_revoke_does_not_invent_a_revocation(
        self, client, monkeypatch, db_factory
    ):
        """Force bypasses the guard, it does not fabricate a result: if the
        provider still reports the user's roles, nothing changes.
        """
        _wire(monkeypatch, db_factory, is_admin=True)
        user_id = await _seed_target(db_factory, roles_raw=[ROLE_RAW])
        _mock_accred_returning(monkeypatch, [ROLE_RAW])

        r = client.post(REVOKE_URL.format(user_id=user_id))

        assert r.status_code == 200, r.text
        assert r.json()["outcome"] == "no_change"

    @pytest.mark.asyncio
    async def test_provider_with_no_out_of_band_source_400s(
        self, client, monkeypatch, db_factory
    ):
        user_id = await _seed_target(
            db_factory, roles_raw=[ROLE_RAW], provider=UserProvider.DEFAULT
        )
        _wire(monkeypatch, db_factory, is_admin=True)
        provider = AsyncMock()
        provider.supports_background_sync = False
        monkeypatch.setattr(
            "app.api.v1.users.get_role_provider", lambda *_args, **_kw: provider
        )

        r = client.post(REVOKE_URL.format(user_id=user_id))

        assert r.status_code == 400, r.text
