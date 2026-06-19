---
status: proposed
last_updated: 2026-06-19
title: "API Connect: connectors and encrypted connections — implementation plan"
summary: "Tiered TDD plan for a modular connector registry, one encrypted connection per connector (entered in the form), per-module connector_luid datasources, the travel + new headcount providers driven from them, and the shared Tableau logic in one base provider."
---

# API Connect: connectors and encrypted connections — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backoffice "API connect" form functional — a hardcoded,
modular connector registry; one encrypted connection per connector (entered
in the form); a `connector_luid` datasource per module; and the travel +
new headcount providers driven from them via one shared base provider.

**Architecture:** `ConnectorType` + a `CONNECTORS` registry name the
integration types (today only `EPFL_TABLEAU`). A `connector_connections`
table holds the connection (`secret_value` Fernet-encrypted); a
`connector_datasources` table holds one `connector_luid` per module. A
`BaseTableauApiProvider` lifts all shared Tableau plumbing out of the travel
provider and adds `_ensure_credentials()`, which loads the datasource +
connection from the DB and reads runtime knobs from settings instead of
reading credentials from env. The factory routes each module's API ingestion
to the right subclass.

**Tech Stack:** FastAPI, SQLModel, async SQLAlchemy, Alembic, Pydantic v2,
`cryptography` (Scrypt + Fernet), pytest; Vue 3 + Quasar 2 frontend.

See the PRD for context and decisions:
[1552-api-connect-tableau-credentials-prd.md](1552-api-connect-tableau-credentials-prd.md).

## Global Constraints

- **Encryption key is dedicated and fails closed.** `CREDENTIALS_ENCRYPTION_KEY`
  - `CREDENTIALS_ENCRYPTION_SALT`; if either is unset, encrypt/decrypt raise.
    Never reuse `SECRET_KEY`.
- **Only `secret_value` is encrypted.** All other connection fields are
  identifiers, stored plaintext.
- **Read schemas never expose `secret_value`.** Expose a boolean
  `has_secret`. The form secret field is write-only; an empty value on update
  keeps the stored secret.
- **Runtime knobs stay in env.** `TABLEAU_VERIFY_SSL`,
  `TABLEAU_REQUEST_TIMEOUT_SECONDS`, `TABLEAU_REST_MIN_API_VERSION`,
  `TABLEAU_MAX_FIELDS` are read from settings, never stored on the connection.
- **No backward compat.** Remove env-var credential reads
  (`TABLEAU_SERVER_URL`, `…SITE_CONTENT_URL`, `…USERNAME`,
  `…CONNECTED_APP_*`, `…DS_FLIGHTS_LUID`) from the travel provider once the DB
  path works (project is pre-v1.x — see memory).
- **No new patterns.** Mirror existing model/repo/service/schema/router
  conventions (`models/user.py`, `repositories/unit_repo.py`,
  `services/data_entry_service.py`, `schemas/user.py`).
- **Backend style:** functions ≤40 lines / ≤2 nesting; wrap column refs in
  `col()`; `# type: ignore[code]` always with a code; narrow with
  `if x is None: raise ...`, never bare `assert`.
- **Every bug/edge fix ships a regression test.**
- **Verification per backend task:** `cd backend && uv run pytest <path> -v`
  then `make type-check` and `make lint`. The user runs the full suite —
  stop at lint/type-check.
- **Frontend has no JS unit harness** (see memory). Verify with
  `cd frontend && make type-check` and `npm run lint`.
- **Migrations via `make db-revision`** — never hand-author; prune any
  false-positive `drop_index` lines after autogenerate.
- **PRs target `dev`.** Each tier below is one PR.

---

## File structure

New backend files:

- `backend/app/core/crypto.py` — encrypt/decrypt helpers.
- `backend/app/models/connector.py` — `ConnectorType` enum + both tables.
- `backend/app/services/data_ingestion/connectors.py` — hardcoded
  `CONNECTORS` registry (`ConnectorSpec`).
- `backend/app/repositories/connector_repo.py` — both repos.
- `backend/app/schemas/connector.py` — connection + datasource + spec DTOs.
- `backend/app/services/connector_service.py` — encryption-aware service.
- `backend/app/api/v1/connectors.py` — router.
- `backend/app/services/data_ingestion/api_providers/base_tableau_api_provider.py`
  — shared base provider.
- `backend/app/services/data_ingestion/api_providers/headcount_members_api_provider.py`
  — new provider.
- Tests under `backend/tests/...` mirroring each.

Modified backend files:

- `backend/app/core/config.py` — new credential settings; drop dead Tableau
  connection env vars (Tier 4), keep the knobs.
- `backend/pyproject.toml` — add `cryptography`.
- `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py`
  — subclass the base, drop env reads.
- `backend/app/services/data_ingestion/provider_factory.py` — register
  headcount provider.
- The v1 router aggregator — include the new router.

Frontend (Tier 6):

- `frontend/src/stores/connectors.ts` (new) — API client + state.
- `frontend/src/composables/useDataEntryDialog.ts` — wire submit to save the
  connection + datasource, then dispatch.
- `frontend/src/components/molecules/data-management/DataEntryDialogContent.vue`
  — connector dropdown, the 6-field connection form, the per-module LUID.

---

## Tier 1 — Encryption foundation (PR 1)

Adds the dedicated key settings, the `cryptography` dependency, and the
encrypt/decrypt helpers. Independently testable: round-trip + fail-closed.

### Task 1.1: Add `cryptography` dependency and config settings

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py:165` (after the Tableau block)

- [ ] **Step 1: Add the dependency**

```bash
cd backend && uv add cryptography
```

- [ ] **Step 2: Add settings** after `TABLEAU_MAX_FIELDS` in `config.py`:

```python
    # Credential encryption (required to store connection secrets)
    CREDENTIALS_ENCRYPTION_KEY: str = Field(
        default="",
        description=(
            "URL-safe base64 secret (>=32 bytes) used to derive the Fernet "
            "key that encrypts stored connection secrets. Provide via env or "
            "a secret manager only; never commit."
        ),
    )
    CREDENTIALS_ENCRYPTION_SALT: str = Field(
        default="",
        description=(
            "URL-safe base64 salt (>=16 bytes) for credential key derivation. "
            "Keep stable for the lifetime of the encrypted data."
        ),
    )
```

- [ ] **Step 3: Verify it imports**

Run: `cd backend && uv run python -c "from app.core.config import get_settings; get_settings()"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/core/config.py
git commit -m "feat(config): add credential encryption settings and cryptography dep"
```

### Task 1.2: Encrypt/decrypt helpers (TDD)

**Files:**

- Create: `backend/app/core/crypto.py`
- Test: `backend/tests/core/test_crypto.py`

**Interfaces:**

- Produces: `encrypt_secret(plaintext: str) -> str`,
  `decrypt_secret(token: str) -> str`. Both raise `RuntimeError` when keys
  are unset.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from app.core import crypto


def test_round_trip(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material-please-change")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt-please-change")
    crypto.get_settings.cache_clear()  # settings are lru_cached
    token = crypto.encrypt_secret("super-secret-value")
    assert token != "super-secret-value"
    assert crypto.decrypt_secret(token) == "super-secret-value"


def test_fails_closed_without_key(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "")
    crypto.get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        crypto.encrypt_secret("x")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_crypto.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.crypto`.

- [ ] **Step 3: Implement `crypto.py`**

```python
import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.core.config import get_settings


def _derive_fernet_key() -> bytes:
    """Derive a Fernet key from the dedicated credential key + salt.

    Fails closed: raises if either secret is unset so a connection can never
    be stored or read without configured encryption.
    """
    settings = get_settings()
    key = settings.CREDENTIALS_ENCRYPTION_KEY
    salt = settings.CREDENTIALS_ENCRYPTION_SALT
    if not key or not salt:
        raise RuntimeError(
            "CREDENTIALS_ENCRYPTION_KEY and CREDENTIALS_ENCRYPTION_SALT must "
            "be set to store or read connection secrets"
        )
    kdf = Scrypt(salt=salt.encode(), length=32, n=2**14, r=8, p=1)
    return base64.urlsafe_b64encode(kdf.derive(key.encode()))


def encrypt_secret(plaintext: str) -> str:
    """Return a Fernet token for ``plaintext`` (URL-safe base64 string)."""
    return Fernet(_derive_fernet_key()).encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Return the plaintext for a Fernet ``token`` produced by encrypt."""
    return Fernet(_derive_fernet_key()).decrypt(token.encode()).decode()
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_crypto.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/core/crypto.py backend/tests/core/test_crypto.py
git commit -m "feat(crypto): Fernet encrypt/decrypt for connection secrets"
```

---

## Tier 2 — Data layer: connector registry, models, migration, repos, schemas (PR 2)

### Task 2.1: Connector enum, models, registry

**Files:**

- Create: `backend/app/models/connector.py`
- Create: `backend/app/services/data_ingestion/connectors.py`

**Interfaces:**

- Produces: `ConnectorType` (str enum: `EPFL_TABLEAU`),
  `ConnectorConnection(table=True)`, `ConnectorDatasource(table=True)`,
  `ConnectorSpec`, `CONNECTORS`, `list_connectors()`.

- [ ] **Step 1: Write the models** (mirror `models/user.py` conventions)

```python
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class ConnectorType(str, Enum):
    EPFL_TABLEAU = "EPFL_TABLEAU"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConnectorConnection(SQLModel, table=True):
    """One connection per connector (where + who + connected-app creds).

    ``secret_value`` is stored encrypted (Fernet token); every other column
    is an identifier entered in the form.
    """

    __tablename__ = "connector_connections"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    connector: ConnectorType = Field(
        sa_column=Column(
            SAEnum(ConnectorType, name="connector_type_enum", native_enum=True),
            nullable=False,
            unique=True,
        ),
    )
    label: str = Field(nullable=False)
    server_url: str = Field(nullable=False)
    site_content_url: Optional[str] = Field(default=None, nullable=True)
    username: str = Field(nullable=False)
    client_id: str = Field(nullable=False)
    secret_id: str = Field(nullable=False)
    secret_value_encrypted: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ConnectorDatasource(SQLModel, table=True):
    """One datasource (LUID) for one module, owned by a connection."""

    __tablename__ = "connector_datasources"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    connection_id: int = Field(
        foreign_key="connector_connections.id", nullable=False, index=True
    )
    module_type_id: int = Field(nullable=False, index=True)
    data_entry_type_id: Optional[int] = Field(default=None, nullable=True)
    connector_luid: str = Field(nullable=False)
    label: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 2: Write the hardcoded registry** (`connectors.py`):

```python
from dataclasses import dataclass

from app.models.connector import ConnectorType


@dataclass(frozen=True)
class ConnectorSpec:
    connector: ConnectorType
    label: str
    form_fields: tuple[str, ...]


# Modular registry: a new integration is one more entry here plus a provider
# subclass. The form renders ``form_fields`` for the chosen connector.
CONNECTORS: dict[ConnectorType, ConnectorSpec] = {
    ConnectorType.EPFL_TABLEAU: ConnectorSpec(
        connector=ConnectorType.EPFL_TABLEAU,
        label="EPFL Tableau",
        form_fields=(
            "server_url",
            "site_content_url",
            "username",
            "client_id",
            "secret_id",
            "secret_value",
        ),
    ),
}


def list_connectors() -> list[ConnectorSpec]:
    return list(CONNECTORS.values())
```

- [ ] **Step 3: Register models for metadata discovery.** Add to
      `app/models/__init__.py` (or the Alembic `env.py` import surface):

```python
from app.models.connector import (  # noqa: F401
    ConnectorConnection,
    ConnectorDatasource,
    ConnectorType,
)
```

- [ ] **Step 4: Verify imports**

Run: `cd backend && uv run python -c "from app.services.data_ingestion.connectors import list_connectors; print([c.connector for c in list_connectors()])"`
Expected: `[<ConnectorType.EPFL_TABLEAU: 'EPFL_TABLEAU'>]`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/connector.py backend/app/services/data_ingestion/connectors.py backend/app/models/__init__.py
git commit -m "feat(models): connector type, connection + datasource tables, registry"
```

### Task 2.2: Alembic migration

**Files:**

- Create: `backend/alembic/versions/<generated>.py`

- [ ] **Step 1: Autogenerate**

```bash
cd backend && make db-revision message="connector connections and datasources"
```

- [ ] **Step 2: Review the generated file.** Confirm it creates both tables,
      the unique constraint on `connector_connections.connector`, the FK + index
      on `connector_datasources.connection_id`, and the `connector_type_enum`
      type. Add a partial unique index for one active datasource per module
      target:

```python
    op.create_index(
        "uq_active_datasource_per_module",
        "connector_datasources",
        ["module_type_id", "data_entry_type_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
```

Mirror it in `downgrade()` and prune any false-positive `drop_index` lines on
unrelated tables (see memory: Alembic autogenerate quirk).

- [ ] **Step 3: Apply and verify**

Run: `cd backend && make db-migrate`
Expected: upgrade to head with no error.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): migration for connector connections and datasources"
```

### Task 2.3: Repositories (TDD)

**Files:**

- Create: `backend/app/repositories/connector_repo.py`
- Test: `backend/tests/repositories/test_connector_repo.py`

**Interfaces:**

- Produces:
  `ConnectorConnectionRepository(session)` with
  `get_by_connector(connector) -> Optional[ConnectorConnection]`,
  `get_by_id(id) -> Optional[ConnectorConnection]`,
  `upsert(conn) -> ConnectorConnection`.
- `ConnectorDatasourceRepository(session)` with
  `get_active_for_module(module_type_id, data_entry_type_id) -> Optional[ConnectorDatasource]`,
  `list_for_connection(connection_id) -> list[ConnectorDatasource]`,
  `upsert(ds) -> ConnectorDatasource`.

- [ ] **Step 1: Write the failing test** (reuse the async DB fixture used by
      `tests/repositories/test_unit_repo.py`):

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/repositories/test_connector_repo.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the repos** (mirror `unit_repo.py`):

```python
from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.connector import (
    ConnectorConnection,
    ConnectorDatasource,
    ConnectorType,
)


class ConnectorConnectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_connector(
        self, connector: ConnectorType
    ) -> Optional[ConnectorConnection]:
        result = await self.session.exec(
            select(ConnectorConnection).where(
                col(ConnectorConnection.connector) == connector
            )
        )
        return result.one_or_none()

    async def get_by_id(self, conn_id: int) -> Optional[ConnectorConnection]:
        result = await self.session.exec(
            select(ConnectorConnection).where(
                col(ConnectorConnection.id) == conn_id
            )
        )
        return result.one_or_none()

    async def upsert(self, conn: ConnectorConnection) -> ConnectorConnection:
        self.session.add(conn)
        await self.session.flush()
        await self.session.refresh(conn)
        return conn


class ConnectorDatasourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_for_module(
        self, module_type_id: int, data_entry_type_id: Optional[int] = None
    ) -> Optional[ConnectorDatasource]:
        query = select(ConnectorDatasource).where(
            col(ConnectorDatasource.module_type_id) == module_type_id,
            col(ConnectorDatasource.is_active).is_(True),
        )
        if data_entry_type_id is not None:
            query = query.where(
                col(ConnectorDatasource.data_entry_type_id) == data_entry_type_id
            )
        result = await self.session.exec(query)
        return result.first()

    async def list_for_connection(
        self, connection_id: int
    ) -> list[ConnectorDatasource]:
        result = await self.session.exec(
            select(ConnectorDatasource).where(
                col(ConnectorDatasource.connection_id) == connection_id
            )
        )
        return list(result.all())

    async def upsert(self, ds: ConnectorDatasource) -> ConnectorDatasource:
        self.session.add(ds)
        await self.session.flush()
        await self.session.refresh(ds)
        return ds
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/repositories/test_connector_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/repositories/connector_repo.py backend/tests/repositories/test_connector_repo.py
git commit -m "feat(repo): connector connection + datasource repositories"
```

### Task 2.4: Pydantic schemas

**Files:**

- Create: `backend/app/schemas/connector.py`

**Interfaces:**

- Produces: `ConnectorSpecRead`, `ConnectorConnectionCreate`,
  `ConnectorConnectionUpdate` (`secret_value` optional — blank keeps stored),
  `ConnectorConnectionRead` (no secret; `has_secret: bool`),
  `ConnectorDatasourceCreate`, `ConnectorDatasourceRead`.

- [ ] **Step 1: Write the schemas** (mirror `schemas/user.py`):

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.connector import ConnectorType


class ConnectorSpecRead(BaseModel):
    connector: ConnectorType
    label: str
    form_fields: list[str]


class ConnectorConnectionCreate(BaseModel):
    label: str
    server_url: str
    site_content_url: Optional[str] = None
    username: str
    client_id: str
    secret_id: str
    secret_value: Optional[str] = None  # required on create; blank keeps on update


class ConnectorConnectionRead(BaseModel):
    id: int
    connector: ConnectorType
    label: str
    server_url: str
    site_content_url: Optional[str]
    username: str
    client_id: str
    secret_id: str
    has_secret: bool  # never expose the secret itself
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ConnectorDatasourceCreate(BaseModel):
    module_type_id: int
    data_entry_type_id: Optional[int] = None
    connector_luid: str
    label: str


class ConnectorDatasourceRead(BaseModel):
    id: int
    connection_id: int
    module_type_id: int
    data_entry_type_id: Optional[int]
    connector_luid: str
    label: str
    is_active: bool
```

- [ ] **Step 2: Verify import**

Run: `cd backend && uv run python -c "from app.schemas.connector import ConnectorConnectionRead"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/connector.py
git commit -m "feat(schemas): connector connection + datasource DTOs (secret write-only)"
```

---

## Tier 3 — Service + API (PR 3)

### Task 3.1: Service (TDD)

**Files:**

- Create: `backend/app/services/connector_service.py`
- Test: `backend/tests/services/test_connector_service.py`

**Interfaces:**

- Produces: `ConnectorConnectionService(session)` with
  `get_by_connector(connector) -> Optional[ConnectorConnection]`,
  `save_connection(connector, payload) -> ConnectorConnection`
  (encrypts `secret_value`; blank `secret_value` on an existing row keeps the
  stored secret),
  `to_read(conn) -> ConnectorConnectionRead`,
  `get_decrypted_secret(conn) -> str`,
  `save_datasource(connection_id, payload) -> ConnectorDatasource`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.core import crypto
from app.models.connector import ConnectorType
from app.schemas.connector import ConnectorConnectionCreate
from app.services.connector_service import ConnectorConnectionService


@pytest.mark.asyncio
async def test_save_encrypts_blank_keeps_and_read_hides_secret(
    db_session, monkeypatch
):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    crypto.get_settings.cache_clear()

    service = ConnectorConnectionService(db_session)
    base = ConnectorConnectionCreate(
        label="EPFL Tableau",
        server_url="https://tableau.epfl.ch/",
        site_content_url="co2fp",
        username="svc-calcco2-epfl-api",
        client_id="cid",
        secret_id="sid",
        secret_value="the-real-secret",
    )
    conn = await service.save_connection(ConnectorType.EPFL_TABLEAU, base)
    await db_session.commit()
    assert conn.secret_value_encrypted != "the-real-secret"
    assert service.get_decrypted_secret(conn) == "the-real-secret"

    # blank secret on update keeps the stored value
    base.username = "changed"
    base.secret_value = None
    conn2 = await service.save_connection(ConnectorType.EPFL_TABLEAU, base)
    await db_session.commit()
    assert conn2.username == "changed"
    assert service.get_decrypted_secret(conn2) == "the-real-secret"

    read = service.to_read(conn2)
    assert read.has_secret is True
    assert not hasattr(read, "secret_value")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_connector_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the service**

```python
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.connector import (
    ConnectorConnection,
    ConnectorDatasource,
    ConnectorType,
)
from app.repositories.connector_repo import (
    ConnectorConnectionRepository,
    ConnectorDatasourceRepository,
)
from app.schemas.connector import (
    ConnectorConnectionCreate,
    ConnectorConnectionRead,
    ConnectorDatasourceCreate,
)


class ConnectorConnectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConnectorConnectionRepository(session)
        self.datasources = ConnectorDatasourceRepository(session)

    async def get_by_connector(
        self, connector: ConnectorType
    ) -> Optional[ConnectorConnection]:
        return await self.repo.get_by_connector(connector)

    async def save_connection(
        self, connector: ConnectorType, payload: ConnectorConnectionCreate
    ) -> ConnectorConnection:
        """Create or replace the single connection for a connector.

        A blank ``secret_value`` on an existing row keeps the stored secret;
        on a new row it is required.
        """
        existing = await self.repo.get_by_connector(connector)
        if existing is None and not payload.secret_value:
            raise ValueError("secret_value is required for a new connection")
        target = existing or ConnectorConnection(
            connector=connector, secret_value_encrypted="",
            label=payload.label, server_url=payload.server_url,
            username=payload.username, client_id=payload.client_id,
            secret_id=payload.secret_id,
        )
        target.label = payload.label
        target.server_url = payload.server_url
        target.site_content_url = payload.site_content_url
        target.username = payload.username
        target.client_id = payload.client_id
        target.secret_id = payload.secret_id
        if payload.secret_value:
            target.secret_value_encrypted = encrypt_secret(payload.secret_value)
        return await self.repo.upsert(target)

    def get_decrypted_secret(self, conn: ConnectorConnection) -> str:
        return decrypt_secret(conn.secret_value_encrypted)

    def to_read(self, conn: ConnectorConnection) -> ConnectorConnectionRead:
        if conn.id is None:
            raise ValueError("connection must be persisted before read")
        return ConnectorConnectionRead(
            id=conn.id,
            connector=conn.connector,
            label=conn.label,
            server_url=conn.server_url,
            site_content_url=conn.site_content_url,
            username=conn.username,
            client_id=conn.client_id,
            secret_id=conn.secret_id,
            has_secret=bool(conn.secret_value_encrypted),
            is_active=conn.is_active,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
        )

    async def save_datasource(
        self, connection_id: int, payload: ConnectorDatasourceCreate
    ) -> ConnectorDatasource:
        existing = await self.datasources.get_active_for_module(
            payload.module_type_id, payload.data_entry_type_id
        )
        target = existing or ConnectorDatasource(
            connection_id=connection_id,
            module_type_id=payload.module_type_id,
            data_entry_type_id=payload.data_entry_type_id,
            connector_luid=payload.connector_luid,
            label=payload.label,
        )
        target.connection_id = connection_id
        target.connector_luid = payload.connector_luid
        target.label = payload.label
        return await self.datasources.upsert(target)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_connector_service.py -v`
Expected: PASS.

- [ ] **Step 5: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/services/connector_service.py backend/tests/services/test_connector_service.py
git commit -m "feat(service): encryption-aware connector connection service"
```

### Task 3.2: Router (TDD)

**Files:**

- Create: `backend/app/api/v1/connectors.py`
- Modify: the v1 router aggregator (mirror how `files.router` is included).
- Test: `backend/tests/api/test_connectors.py`

**Interfaces:**

- Produces these routes (all under the backoffice permission gate already
  used by `/sync/dispatch` — locate that dependency in `api/v1/data_sync.py`
  and reuse it verbatim):
  - `GET /api/v1/connectors` → `list[ConnectorSpecRead]`
  - `GET /api/v1/connectors/{connector}/connection` → `ConnectorConnectionRead | null`
  - `PUT /api/v1/connectors/{connector}/connection` (body `ConnectorConnectionCreate`) → `ConnectorConnectionRead`
  - `POST /api/v1/connectors/{connector}/datasources` (body `ConnectorDatasourceCreate`) → `ConnectorDatasourceRead`
  - `POST /api/v1/connectors/{connector}/test` → `{ "ok": bool, "detail": str }`

- [ ] **Step 1: Write the failing test** (reuse the authed client fixtures
      from `tests/api/test_files.py` or similar):

```python
import pytest


@pytest.mark.asyncio
async def test_list_then_put_then_get_hides_secret(authed_client, monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    from app.core import crypto

    crypto.get_settings.cache_clear()

    listed = await authed_client.get("/api/v1/connectors")
    assert listed.status_code == 200
    assert listed.json()[0]["connector"] == "EPFL_TABLEAU"

    body = {
        "label": "EPFL Tableau",
        "server_url": "https://tableau.epfl.ch/",
        "site_content_url": "co2fp",
        "username": "svc-calcco2-epfl-api",
        "client_id": "cid",
        "secret_id": "sid",
        "secret_value": "the-real-secret",
    }
    put = await authed_client.put(
        "/api/v1/connectors/EPFL_TABLEAU/connection", json=body
    )
    assert put.status_code == 200
    assert "secret_value" not in put.json()
    assert put.json()["has_secret"] is True

    got = await authed_client.get("/api/v1/connectors/EPFL_TABLEAU/connection")
    assert got.status_code == 200
    assert got.json()["client_id"] == "cid"
    assert "secret_value" not in got.json()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_connectors.py -v`
Expected: FAIL — 404 (routes not registered).

- [ ] **Step 3: Implement the router**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_data_session  # match the existing session dep
from app.models.connector import ConnectorType
from app.schemas.connector import (
    ConnectorConnectionCreate,
    ConnectorConnectionRead,
    ConnectorDatasourceCreate,
    ConnectorDatasourceRead,
    ConnectorSpecRead,
)
from app.services.connector_service import ConnectorConnectionService
from app.services.data_ingestion.connectors import list_connectors

# require_backoffice_data_management: reuse the SAME dependency that gates
# POST /sync/dispatch (see app/api/v1/data_sync.py). Deny by default.
from app.api.v1.data_sync import require_backoffice_data_management

router = APIRouter(
    prefix="/connectors",
    tags=["connectors"],
    dependencies=[Depends(require_backoffice_data_management)],
)


@router.get("", response_model=list[ConnectorSpecRead])
async def get_connectors():
    return [
        ConnectorSpecRead(
            connector=s.connector, label=s.label, form_fields=list(s.form_fields)
        )
        for s in list_connectors()
    ]


@router.get(
    "/{connector}/connection", response_model=ConnectorConnectionRead | None
)
async def get_connection(
    connector: ConnectorType,
    db: AsyncSession = Depends(get_data_session),
):
    service = ConnectorConnectionService(db)
    conn = await service.get_by_connector(connector)
    return service.to_read(conn) if conn else None


@router.put("/{connector}/connection", response_model=ConnectorConnectionRead)
async def upsert_connection(
    connector: ConnectorType,
    payload: ConnectorConnectionCreate,
    db: AsyncSession = Depends(get_data_session),
):
    service = ConnectorConnectionService(db)
    conn = await service.save_connection(connector, payload)
    await db.commit()
    return service.to_read(conn)


@router.post(
    "/{connector}/datasources", response_model=ConnectorDatasourceRead
)
async def upsert_datasource(
    connector: ConnectorType,
    payload: ConnectorDatasourceCreate,
    db: AsyncSession = Depends(get_data_session),
):
    service = ConnectorConnectionService(db)
    conn = await service.get_by_connector(connector)
    if conn is None or conn.id is None:
        raise HTTPException(status_code=404, detail="connection not found")
    ds = await service.save_datasource(conn.id, payload)
    await db.commit()
    return ConnectorDatasourceRead.model_validate(ds, from_attributes=True)


@router.post("/{connector}/test")
async def test_connection(
    connector: ConnectorType,
    db: AsyncSession = Depends(get_data_session),
):
    from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
        BaseTableauApiProvider,
    )

    ok, detail = await BaseTableauApiProvider.test_connection(db, connector)
    return {"ok": ok, "detail": detail}
```

> **Note.** Wire `/test` last — it depends on Tier 4's
> `BaseTableauApiProvider.test_connection`. If implementing Tier 3 first, stub
> it to `{"ok": false, "detail": "not yet wired"}` and replace in Tier 4.

- [ ] **Step 4: Register the router** in the v1 aggregator (same place
      `files.router` is included):

```python
from app.api.v1 import connectors
app.include_router(connectors.router, prefix="/api/v1")
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_connectors.py -v`
Expected: PASS.

- [ ] **Step 6: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/api/v1/connectors.py backend/tests/api/test_connectors.py <aggregator>
git commit -m "feat(api): connectors registry + connection + datasource endpoints"
```

---

## Tier 4 — Base Tableau provider + travel migration (PR 4)

Lift the shared plumbing into a base class and feed the travel provider from
the DB. Travel behaviour is unchanged; the source of credentials changes.

### Task 4.1: `BaseTableauApiProvider`

**Files:**

- Create: `backend/app/services/data_ingestion/api_providers/base_tableau_api_provider.py`

**Interfaces:**

- Consumes: `ConnectorConnectionService`, `get_settings`.
- Produces a base class with:
  - class attrs (override per subclass): `CONNECTOR: ConnectorType`,
    `MODULE_TYPE: ModuleTypeEnum`, `DATA_ENTRY_TYPE: DataEntryTypeEnum`,
    `REQUIRED_CAPTIONS: list[str]`.
  - `async _ensure_credentials() -> None` — loads datasource + connection
    once; sets `self.server_url`, `self.site_content_url`, `self.username`,
    `self.client_id`, `self.secret_id`, `self.secret_value`,
    `self.datasource_luid`; reads `self.verify_ssl`, `self.timeout`,
    `self.min_api_version` from settings. Raises `ValueError` with a clear
    message if no connection/datasource exists.
  - `async validate_connection() -> bool`, `async fetch_data(filters)`
    (generic: ensure creds → read-metadata → validate `REQUIRED_CAPTIONS` →
    query → rows).
  - moved helpers (verbatim from the travel provider): `_generate_jwt`,
    `_signin_with_jwt`, `_create_session`, `_vds_read_metadata`,
    `_extract_field_captions`, `_build_payload`, `_vds_query_datasource`,
    `_resolve_carbon_report_modules`, `_record_row_error`,
    `normalize_vds_payload`, `to_bool`.
  - `@classmethod async test_connection(db, connector) -> tuple[bool, str]`.
  - abstract: `transform_data`, `_build_data_entry(record, carbon_report_module_id) -> DataEntry`.

- [ ] **Step 1: Create the base class.** Move, verbatim, these methods from
      `professional_travel_api_provider.py` into the base (cut from the named
      ranges, do not rewrite):
  - `normalize_vds_payload` (lines 64-85), `to_bool` (lines 914-915)
  - `_generate_jwt` (545-583), `_signin_with_jwt` (585-659),
    `_create_session` (661-673), `_vds_read_metadata` (675-691),
    `_extract_field_captions` (693-722), `_build_payload` (724-739),
    `_vds_query_datasource` (741-754), `_record_row_error` (899-911),
    `_resolve_carbon_report_modules` (773-897).

  Replace every `self.settings.TABLEAU_*` read with the instance attrs that
  `_ensure_credentials` sets. Add the new credential loader:

```python
    async def _ensure_credentials(self) -> None:
        """Load the connection + per-module datasource from the DB once."""
        if getattr(self, "_credentials_loaded", False):
            return
        service = ConnectorConnectionService(self.data_session)
        conn = await service.get_by_connector(self.CONNECTOR)
        if conn is None:
            raise ValueError(
                f"No {self.CONNECTOR.value} connection configured — set one in "
                "the API connect form before importing."
            )
        ds = await service.datasources.get_active_for_module(
            int(self.MODULE_TYPE), self.config.get("data_entry_type_id")
        )
        if ds is None:
            raise ValueError(
                f"No datasource (LUID) set for module {self.MODULE_TYPE.name} "
                "— set one in the API connect form."
            )
        settings = get_settings()
        self.server_url = conn.server_url
        self.site_content_url = conn.site_content_url
        self.username = conn.username
        self.client_id = conn.client_id
        self.secret_id = conn.secret_id
        self.secret_value = service.get_decrypted_secret(conn)
        self.verify_ssl = self.to_bool(settings.TABLEAU_VERIFY_SSL)
        self.timeout = int(settings.TABLEAU_REQUEST_TIMEOUT_SECONDS)
        self.min_api_version = settings.TABLEAU_REST_MIN_API_VERSION
        self.datasource_luid = ds.connector_luid
        self.module_type_id = self.config.get("module_type_id")
        self._credentials_loaded = True
```

`validate_connection` and `fetch_data` call `await self._ensure_credentials()`
first, then run the moved logic (same bodies as today, minus the env reads).
Note: `_signin_with_jwt` reads `self.username` (was `self.settings.TABLEAU_USERNAME`).

- [ ] **Step 2: Add the classmethod connection test**

```python
    @classmethod
    async def test_connection(
        cls, db: AsyncSession, connector: ConnectorType
    ) -> tuple[bool, str]:
        service = ConnectorConnectionService(db)
        conn = await service.get_by_connector(connector)
        if conn is None:
            return False, "No connection configured"
        # Build a throwaway instance bound to the connection fields and try a
        # JWT sign-in (no datasource needed). See the Step 3 test for the
        # asserted contract.
        ...
```

- [ ] **Step 3: Write a unit test** that monkeypatches `_signin_with_jwt` to
      return a token and asserts `validate_connection()` is True after a
      connection + datasource row exist; and asserts a clear `ValueError` when no
      connection is configured. File:
      `backend/tests/services/data_ingestion/test_base_tableau_provider.py`.

- [ ] **Step 4: Run the test**

Run: `cd backend && uv run pytest tests/services/data_ingestion/test_base_tableau_provider.py -v`
Expected: PASS.

- [ ] **Step 5: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/services/data_ingestion/api_providers/base_tableau_api_provider.py backend/tests/services/data_ingestion/test_base_tableau_provider.py
git commit -m "feat(ingestion): BaseTableauApiProvider with DB-backed connection"
```

### Task 4.2: Migrate `ProfessionalTravelApiProvider` onto the base

**Files:**

- Modify: `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py`

- [ ] **Step 1: Reduce the class to its module-specific surface.** It now
      subclasses `BaseTableauApiProvider` and keeps only:
  - class attrs: `CONNECTOR = ConnectorType.EPFL_TABLEAU`,
    `MODULE_TYPE = ModuleTypeEnum.professional_travel`,
    `DATA_ENTRY_TYPE = DataEntryTypeEnum.plane`,
    `REQUIRED_CAPTIONS = [...]` (unchanged list).
  - `transform_data` (unchanged), `ingest` (unchanged orchestration),
    `_load_data` (unchanged — the `OUT_CO2_CORRECTED` / `KG_CO2EQ_OVERRIDE_KEY`
    carrier logic), `_parse_date`, `_normalize_class`.
  - Delete `__init__`'s env reads and every moved helper.

- [ ] **Step 2: Run the existing travel provider tests**

Run: `cd backend && uv run pytest tests/ -k "professional_travel or travel_api" -v`
Expected: PASS (behaviour unchanged). If a test stubbed `get_settings`
Tableau values, update it to seed a `ConnectorConnection` +
`ConnectorDatasource` instead.

- [ ] **Step 3: Remove now-dead env settings.** Grep first, then drop the
      connection env vars no longer referenced — `TABLEAU_SERVER_URL`,
      `TABLEAU_SITE_CONTENT_URL`, `TABLEAU_USERNAME`,
      `TABLEAU_CONNECTED_APP_CLIENT_ID/SECRET_ID/SECRET_VALUE`,
      `TABLEAU_DS_FLIGHTS_LUID` — from `config.py`. **Keep** the knobs
      (`TABLEAU_VERIFY_SSL`, `TABLEAU_REQUEST_TIMEOUT_SECONDS`,
      `TABLEAU_REST_MIN_API_VERSION`, `TABLEAU_MAX_FIELDS`).

```bash
cd backend && rtk grep "TABLEAU_" app/
```

(No backward compat — see memory.)

- [ ] **Step 4: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py backend/app/core/config.py
git commit -m "refactor(ingestion): drive travel provider from DB connection"
```

---

## Tier 5 — Headcount members API provider (PR 5)

### Task 5.1: `HeadcountMembersApiProvider` (TDD)

**Files:**

- Create: `backend/app/services/data_ingestion/api_providers/headcount_members_api_provider.py`
- Modify: `backend/app/services/data_ingestion/provider_factory.py`
- Test: `backend/tests/services/data_ingestion/test_headcount_members_api_provider.py`

**Interfaces:**

- Consumes: `BaseTableauApiProvider`, `HeadCountCreate`
  (`name`, `sius_code`, `user_institutional_id`, `fte`).
- Produces a provider registered at
  `(ModuleTypeEnum.headcount, IngestionMethod.api, TargetType.DATA_ENTRIES, EntityType.MODULE_PER_YEAR)`.

> **Captions are datasource-defined.** The exact Tableau `fieldCaption`
> values for the headcount datasource are unknown until read-metadata is run
> against its LUID. The transform **target** is fixed (the `member` row).
> Set the headcount `connector_luid` via the form, run read-metadata through
> the base provider in a REPL, then fill the `CAPTION_*` constants below from
> the real metadata.

- [ ] **Step 1: Write the failing transform test** (pins the mapping, not the
      datasource — captions parametrized as constants):

```python
import pytest

from app.services.data_ingestion.api_providers.headcount_members_api_provider import (
    HeadcountMembersApiProvider,
)


@pytest.mark.asyncio
async def test_transform_maps_member_fields(db_session):
    provider = HeadcountMembersApiProvider(
        config={"module_type_id": 1, "year": 2025},
        user=None,
        data_session=db_session,
    )
    raw = [
        {
            HeadcountMembersApiProvider.CAPTION_NAME: "Role Std",
            HeadcountMembersApiProvider.CAPTION_SCIPER: "123456",
            HeadcountMembersApiProvider.CAPTION_SIUS: "51",
            HeadcountMembersApiProvider.CAPTION_FTE: "0.5",
            HeadcountMembersApiProvider.CAPTION_UNIT: "F0828",
        }
    ]
    out = await provider.transform_data(raw)
    assert out[0]["user_institutional_id"] == "123456"
    assert out[0]["fte"] == 0.5
    assert out[0]["sius_code"] == "51"
    assert out[0]["unit_institutional_id"] == "0828"  # prefix stripped
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/services/data_ingestion/test_headcount_members_api_provider.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the provider**

```python
from typing import Any, Dict, List

from app.models.connector import ConnectorType
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
    BaseTableauApiProvider,
)


class HeadcountMembersApiProvider(BaseTableauApiProvider):
    CONNECTOR = ConnectorType.EPFL_TABLEAU
    MODULE_TYPE = ModuleTypeEnum.headcount
    DATA_ENTRY_TYPE = DataEntryTypeEnum.member

    # Fill these from read-metadata against the headcount connector_luid.
    CAPTION_NAME = "Name"
    CAPTION_SCIPER = "SCIPER"
    CAPTION_SIUS = "SIUS"
    CAPTION_FTE = "FTE"
    CAPTION_UNIT = "Centre financier"

    REQUIRED_CAPTIONS = [
        CAPTION_NAME,
        CAPTION_SCIPER,
        CAPTION_SIUS,
        CAPTION_FTE,
        CAPTION_UNIT,
    ]

    @staticmethod
    def _strip_unit_prefix(unit_id: str | None) -> str | None:
        if not unit_id:
            return unit_id
        if len(unit_id) > 1 and unit_id[0].isalpha() and unit_id[1:].isdigit():
            return unit_id[1:]
        return unit_id

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        transformed: List[Dict[str, Any]] = []
        for record in raw_data:
            sciper = record.get(self.CAPTION_SCIPER)
            if not sciper or str(sciper).strip() == "":
                continue
            raw_fte = record.get(self.CAPTION_FTE)
            try:
                fte = float(raw_fte) if raw_fte is not None else None
            except (ValueError, TypeError):
                fte = None
            if fte is None:
                continue
            transformed.append(
                {
                    "unit_institutional_id": self._strip_unit_prefix(
                        record.get(self.CAPTION_UNIT)
                    ),
                    "user_institutional_id": str(sciper),
                    "name": record.get(self.CAPTION_NAME) or "",
                    "sius_code": str(record.get(self.CAPTION_SIUS) or ""),
                    "fte": fte,
                    "note": None,
                }
            )
        return transformed

    def _build_data_entry(
        self, record: Dict[str, Any], carbon_report_module_id: int
    ) -> DataEntry:
        return DataEntry(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            data={
                "name": record["name"],
                "sius_code": record["sius_code"],
                "user_institutional_id": record["user_institutional_id"],
                "fte": record["fte"],
                "note": record.get("note"),
            },
        )

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Mirror the travel provider's bulk path, minus the kg_co2eq override
        # (headcount carries no emission override). Build member DataEntry rows
        # via _build_data_entry and bulk_create with source
        # EXTERNAL_INTEGRATION. See professional_travel_api_provider._load_data
        # for the bulk_create call shape.
        ...
```

Implement `ingest` by reusing the travel provider's orchestration shape
(`fetch → transform → _resolve_carbon_report_modules → inject
  carbon_report_module_id → _load_data`). If both providers end up identical
except for `_build_data_entry`, lift the orchestration into
`BaseTableauApiProvider.ingest`; else keep a thin override.

- [ ] **Step 4: Register in the factory** — add to `PROVIDERS` in
      `provider_factory.py` after the travel entry (line 94):

```python
        (
            ModuleTypeEnum.headcount,
            IngestionMethod.api,
            TargetType.DATA_ENTRIES,
            EntityType.MODULE_PER_YEAR,
        ): HeadcountMembersApiProvider,
```

and import it at the top of the file.

- [ ] **Step 5: Run the tests**

Run: `cd backend && uv run pytest tests/services/data_ingestion/test_headcount_members_api_provider.py -v`
Expected: PASS.

- [ ] **Step 6: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/services/data_ingestion/api_providers/headcount_members_api_provider.py backend/app/services/data_ingestion/provider_factory.py backend/tests/services/data_ingestion/test_headcount_members_api_provider.py
git commit -m "feat(ingestion): headcount members Tableau API provider"
```

---

## Tier 6 — Frontend: wire the form (PR 6)

Make the dialog pick a connector, save the connection + datasource, then
dispatch. No JS unit harness — verify with `make type-check` and
`npm run lint`, then a manual walkthrough.

### Task 6.1: Connectors store/client

**Files:**

- Create: `frontend/src/stores/connectors.ts`

- [ ] **Step 1:** Add a Pinia store with typed calls mirroring
      `stores/backofficeDataManagement.ts` axios usage:
  - `listConnectors()` → `GET /connectors`
  - `getConnection(connector)` → `GET /connectors/{connector}/connection`
  - `saveConnection(connector, payload)` → `PUT /connectors/{connector}/connection`
  - `saveDatasource(connector, payload)` → `POST /connectors/{connector}/datasources`
  - `testConnection(connector)` → `POST /connectors/{connector}/test`
    Generate types from OpenAPI if the repo uses `openapi-typescript` (see plan
    `217-openapi-typescript-typegen.md`); else hand-type to the Read schemas.

- [ ] **Step 2:** `cd frontend && make type-check && npm run lint`
- [ ] **Step 3:** Commit.

### Task 6.2: Extend the dialog form

**Files:**

- Modify: `frontend/src/components/molecules/data-management/DataEntryDialogContent.vue:151-202`
- Modify: `frontend/src/composables/useDataEntryDialog.ts:33-148`

- [ ] **Step 1:** Replace the API-connect section with:
  - a connector select (one entry today, from `listConnectors()`);
  - the connection form fields driven by the connector's `form_fields`:
    `server_url`, `site_content_url`, `username`, `client_id`, `secret_id`,
    `secret_value` (secret as a `password` input, write-only);
  - a `connector_luid` input for this module.
    On open, call `getConnection(connector)`; if present, prefill non-secret
    fields and leave `secret_value` blank with a "secret set — leave blank to
    keep" hint.

- [ ] **Step 2:** Replace `connectAndSync()` so it:
  1. `await saveConnection(connector, {...})` (omit `secret_value` if left
     blank on edit — the service keeps the stored secret).
  2. `await saveDatasource(connector, { module_type_id, connector_luid, label })`.
  3. `await initiateSync('api')` — unchanged dispatch; the provider now loads
     the connection + datasource from the DB, so `config` stays as today.

- [ ] **Step 3:** Add the new i18n keys
      (`data_management_api_connector`, `..._site_content_url`, `..._username`,
      `..._luid`, `..._secret_kept`) to
      `frontend/src/i18n/backoffice_data_management.ts` and every locale.

- [ ] **Step 4:** `cd frontend && make type-check && npm run lint`
- [ ] **Step 5:** Manual walkthrough: open dialog for plane_travel → pick
      connector → enter connection + LUID → "API Connect and Sync" → job succeeds
      via SSE. Repeat for headcount.
- [ ] **Step 6:** Commit.

---

## Self-review checklist (run before opening PRs)

- **Spec coverage:** Goal 1 → Tiers 1-2; Goal 2 → Tier 3; Goal 3 → Tier 4;
  Goal 4 → Tier 5; Goal 5 → Tier 4 base class + Tier 2 registry. Frontend →
  Tier 6.
- **Secret never leaves the server in plaintext:** no Read schema or log
  statement includes `secret_value` / `secret_value_encrypted`; blank
  `secret_value` on update keeps the stored value.
- **Fail-closed:** with keys unset, `PUT .../connection` returns 500 and no
  row is written.
- **Knobs in env:** the provider reads `verify_ssl` / `timeout` /
  `api_version` / `max_fields` from settings, not from the connection row.
- **Type consistency:** `CONNECTOR` / `MODULE_TYPE` / `DATA_ENTRY_TYPE` class
  attrs match between base and both subclasses; factory key tuple matches the
  registered `(module_type, method, target, entity)`; `connector_luid` is the
  field name everywhere.
- **Docs:** update the data-management docs page in the same PR as Tier 6;
  link this plan from the PRD (done).
