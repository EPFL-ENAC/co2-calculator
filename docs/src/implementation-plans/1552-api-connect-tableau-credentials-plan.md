---
status: proposed
last_updated: 2026-06-19
title: "API Connect: encrypted Tableau credentials — implementation plan"
summary: "Tiered TDD plan to store an encrypted shared Tableau connection plus per-module datasource bindings, drive the travel + new headcount API providers from them, and DRY the shared Tableau logic into one base provider."
---

# API Connect: encrypted Tableau credentials — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backoffice "API connect" form functional — store one
shared, encrypted Tableau connection and per-module datasource (LUID)
bindings, then drive `ProfessionalTravelApiProvider` and a new
`HeadcountMembersApiProvider` from them via one shared base provider.

**Architecture:** A new `external_connections` table holds the shared
connected-app credentials (`secret_value` Fernet-encrypted); a new
`external_datasource_bindings` table holds one LUID per module. A
`BaseTableauApiProvider` lifts all shared Tableau plumbing out of the travel
provider and adds `_ensure_credentials()`, which loads the binding + decrypted
connection at runtime instead of reading env vars. The factory routes each
module's API ingestion to the right subclass.

**Tech Stack:** FastAPI, SQLModel, async SQLAlchemy, Alembic, Pydantic v2,
`cryptography` (Scrypt + Fernet), pytest; Vue 3 + Quasar 2 frontend.

See the PRD for context and decisions:
[1552-api-connect-tableau-credentials-prd.md](1552-api-connect-tableau-credentials-prd.md).

## Global Constraints

- **Encryption key is dedicated and fails closed.** `CREDENTIALS_ENCRYPTION_KEY`
  - `CREDENTIALS_ENCRYPTION_SALT`; if either is unset, encrypt/decrypt raise.
    Never reuse `SECRET_KEY`.
- **Only `secret_value` is encrypted.** All other connection fields are
  identifiers or operational knobs, stored plaintext.
- **Read schemas never expose `secret_value`.** Expose a boolean
  `has_secret` instead. The frontend secret field is write-only.
- **No backward compat.** Remove env-var credential reads from the travel
  provider once the DB path works (project is pre-v1.x — see memory).
- **No new patterns.** Mirror existing model/repo/service/schema/router
  conventions (`models/user.py`, `repositories/unit_repo.py`,
  `services/data_entry_service.py`, `schemas/user.py`).
- **Backend style:** functions ≤40 lines / ≤2 nesting; wrap column refs in
  `col()`; `# type: ignore[code]` always with a code; narrow with
  `if x is None: raise ...`, never bare `assert`.
- **Every bug/edge fix ships a regression test.**
- **Verification per backend task:** `cd backend && uv run pytest <path> -v`
  then `cd backend && make type-check` and `make lint`. The user runs the
  full suite — stop at lint/type-check.
- **Frontend has no JS unit harness** (see memory). Verify with
  `cd frontend && make type-check` and `npm run lint`.
- **Migrations via `make db-revision`** — never hand-author; prune any
  false-positive `drop_index` lines after autogenerate.
- **PRs target `dev`.** Each tier below is one PR.

---

## File structure

New backend files:

- `backend/app/core/crypto.py` — encrypt/decrypt helpers.
- `backend/app/models/external_connection.py` — both tables + provider enum.
- `backend/app/repositories/external_connection_repo.py` — both repos.
- `backend/app/schemas/external_connection.py` — Read/Create/Update + binding
  schemas.
- `backend/app/services/external_connection_service.py` — encryption-aware
  service.
- `backend/app/api/v1/external_connections.py` — router.
- `backend/app/services/data_ingestion/api_providers/base_tableau_api_provider.py`
  — shared base provider.
- `backend/app/services/data_ingestion/api_providers/headcount_members_api_provider.py`
  — new provider.
- Tests under `backend/tests/...` mirroring each.

Modified backend files:

- `backend/app/core/config.py` — new settings.
- `backend/pyproject.toml` — add `cryptography`.
- `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py`
  — subclass the base, drop env reads.
- `backend/app/services/data_ingestion/provider_factory.py` — register
  headcount provider.
- `backend/app/main.py` (or the router aggregator) — include the new router.

Frontend (Tier 6):

- `frontend/src/stores/externalConnections.ts` (new) — API client + state.
- `frontend/src/composables/useDataEntryDialog.ts` — wire submit to save
  connection + binding, then dispatch.
- `frontend/src/components/molecules/data-management/DataEntryDialogContent.vue`
  — add site/username/LUID fields, prefill existing connection.

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
    # Credential encryption (required to store API connection secrets)
    CREDENTIALS_ENCRYPTION_KEY: str = Field(
        default="",
        description=(
            "URL-safe base64 secret (>=32 bytes) used to derive the Fernet "
            "key that encrypts stored API-connection secrets. Provide via env "
            "or a secret manager only; never commit."
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
            "be set to store or read API-connection secrets"
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
git commit -m "feat(crypto): Fernet encrypt/decrypt for API-connection secrets"
```

---

## Tier 2 — Data layer: models, migration, repos, schemas (PR 2)

### Task 2.1: Models + provider enum

**Files:**

- Create: `backend/app/models/external_connection.py`

**Interfaces:**

- Produces: `ExternalProviderType` (str enum: `EPFL_TABLEAU`),
  `ExternalConnection(table=True)`, `ExternalDatasourceBinding(table=True)`.

- [ ] **Step 1: Write the model** (mirror `models/user.py` conventions)

```python
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class ExternalProviderType(str, Enum):
    EPFL_TABLEAU = "EPFL_TABLEAU"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExternalConnection(SQLModel, table=True):
    """A shared connection to an external data provider (Tableau).

    The connected-app ``secret_value`` is stored encrypted (Fernet token);
    every other column is an identifier or an operational knob.
    """

    __tablename__ = "external_connections"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    provider_type: ExternalProviderType = Field(
        sa_column=Column(
            SAEnum(
                ExternalProviderType,
                name="external_provider_type_enum",
                native_enum=True,
            ),
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
    verify_ssl: bool = Field(default=True, nullable=False)
    request_timeout_seconds: int = Field(default=300, nullable=False)
    rest_min_api_version: str = Field(default="2.4", nullable=False)
    max_fields: int = Field(default=50, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ExternalDatasourceBinding(SQLModel, table=True):
    """One datasource (LUID) for one module, owned by a connection."""

    __tablename__ = "external_datasource_bindings"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    connection_id: int = Field(
        foreign_key="external_connections.id", nullable=False, index=True
    )
    module_type_id: int = Field(nullable=False, index=True)
    data_entry_type_id: Optional[int] = Field(default=None, nullable=True)
    datasource_luid: str = Field(nullable=False)
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

- [ ] **Step 2: Register the models for metadata discovery**

Confirm `app/models/__init__.py` (or the Alembic `env.py` import surface)
imports the new module so `SQLModel.metadata` sees both tables. Add:

```python
from app.models.external_connection import (  # noqa: F401
    ExternalConnection,
    ExternalDatasourceBinding,
    ExternalProviderType,
)
```

- [ ] **Step 3: Verify import + metadata**

Run: `cd backend && uv run python -c "from app.models.external_connection import ExternalConnection; print(ExternalConnection.__tablename__)"`
Expected: `external_connections`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/external_connection.py backend/app/models/__init__.py
git commit -m "feat(models): external connection + datasource binding tables"
```

### Task 2.2: Alembic migration

**Files:**

- Create: `backend/alembic/versions/<generated>.py`

- [ ] **Step 1: Autogenerate**

```bash
cd backend && make db-revision message="external connections and datasource bindings"
```

- [ ] **Step 2: Review the generated file**

Confirm it creates both tables, the unique constraint on
`external_connections.provider_type`, the FK and index on
`external_datasource_bindings.connection_id`, and the
`external_provider_type_enum` type. Add a partial unique index for one active
binding per module target:

```python
    op.create_index(
        "uq_active_binding_per_module",
        "external_datasource_bindings",
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
git commit -m "feat(db): migration for external connections and bindings"
```

### Task 2.3: Repositories (TDD)

**Files:**

- Create: `backend/app/repositories/external_connection_repo.py`
- Test: `backend/tests/repositories/test_external_connection_repo.py`

**Interfaces:**

- Produces:
  `ExternalConnectionRepository(session)` with
  `get_by_provider(provider_type) -> Optional[ExternalConnection]`,
  `get_by_id(id) -> Optional[ExternalConnection]`,
  `upsert(conn) -> ExternalConnection`.
- `ExternalDatasourceBindingRepository(session)` with
  `get_active_for_module(module_type_id, data_entry_type_id) -> Optional[ExternalDatasourceBinding]`,
  `list_for_connection(connection_id) -> list[ExternalDatasourceBinding]`,
  `upsert(binding) -> ExternalDatasourceBinding`.

- [ ] **Step 1: Write the failing test** (use the existing async DB fixture —
      copy the fixture import used by `tests/repositories/test_unit_repo.py`):

```python
import pytest

from app.models.external_connection import (
    ExternalConnection,
    ExternalProviderType,
)
from app.repositories.external_connection_repo import (
    ExternalConnectionRepository,
)


@pytest.mark.asyncio
async def test_get_by_provider_returns_saved_connection(db_session):
    repo = ExternalConnectionRepository(db_session)
    saved = await repo.upsert(
        ExternalConnection(
            provider_type=ExternalProviderType.EPFL_TABLEAU,
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
    found = await repo.get_by_provider(ExternalProviderType.EPFL_TABLEAU)
    assert found is not None
    assert found.id == saved.id
    assert found.server_url == "https://tableau.epfl.ch/"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/repositories/test_external_connection_repo.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the repos** (mirror `unit_repo.py`):

```python
from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.external_connection import (
    ExternalConnection,
    ExternalDatasourceBinding,
    ExternalProviderType,
)


class ExternalConnectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_provider(
        self, provider_type: ExternalProviderType
    ) -> Optional[ExternalConnection]:
        result = await self.session.exec(
            select(ExternalConnection).where(
                col(ExternalConnection.provider_type) == provider_type
            )
        )
        return result.one_or_none()

    async def get_by_id(self, conn_id: int) -> Optional[ExternalConnection]:
        result = await self.session.exec(
            select(ExternalConnection).where(col(ExternalConnection.id) == conn_id)
        )
        return result.one_or_none()

    async def upsert(self, conn: ExternalConnection) -> ExternalConnection:
        self.session.add(conn)
        await self.session.flush()
        await self.session.refresh(conn)
        return conn


class ExternalDatasourceBindingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_for_module(
        self, module_type_id: int, data_entry_type_id: Optional[int] = None
    ) -> Optional[ExternalDatasourceBinding]:
        query = select(ExternalDatasourceBinding).where(
            col(ExternalDatasourceBinding.module_type_id) == module_type_id,
            col(ExternalDatasourceBinding.is_active).is_(True),
        )
        if data_entry_type_id is not None:
            query = query.where(
                col(ExternalDatasourceBinding.data_entry_type_id)
                == data_entry_type_id
            )
        result = await self.session.exec(query)
        return result.first()

    async def list_for_connection(
        self, connection_id: int
    ) -> list[ExternalDatasourceBinding]:
        result = await self.session.exec(
            select(ExternalDatasourceBinding).where(
                col(ExternalDatasourceBinding.connection_id) == connection_id
            )
        )
        return list(result.all())

    async def upsert(
        self, binding: ExternalDatasourceBinding
    ) -> ExternalDatasourceBinding:
        self.session.add(binding)
        await self.session.flush()
        await self.session.refresh(binding)
        return binding
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/repositories/test_external_connection_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/repositories/external_connection_repo.py backend/tests/repositories/test_external_connection_repo.py
git commit -m "feat(repo): external connection + binding repositories"
```

### Task 2.4: Pydantic schemas

**Files:**

- Create: `backend/app/schemas/external_connection.py`

**Interfaces:**

- Produces: `ExternalConnectionCreate`, `ExternalConnectionUpdate`,
  `ExternalConnectionRead` (no secret; `has_secret: bool`),
  `DatasourceBindingCreate`, `DatasourceBindingRead`.

- [ ] **Step 1: Write the schemas** (mirror `schemas/user.py`):

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.external_connection import ExternalProviderType


class ExternalConnectionCreate(BaseModel):
    provider_type: ExternalProviderType = ExternalProviderType.EPFL_TABLEAU
    label: str
    server_url: str
    site_content_url: Optional[str] = None
    username: str
    client_id: str
    secret_id: str
    secret_value: str  # plaintext in; encrypted by the service
    verify_ssl: bool = True
    request_timeout_seconds: int = 300
    rest_min_api_version: str = "2.4"
    max_fields: int = 50


class ExternalConnectionUpdate(BaseModel):
    label: Optional[str] = None
    server_url: Optional[str] = None
    site_content_url: Optional[str] = None
    username: Optional[str] = None
    client_id: Optional[str] = None
    secret_id: Optional[str] = None
    secret_value: Optional[str] = None  # only re-encrypt when provided
    verify_ssl: Optional[bool] = None
    request_timeout_seconds: Optional[int] = None
    rest_min_api_version: Optional[str] = None
    max_fields: Optional[int] = None


class ExternalConnectionRead(BaseModel):
    id: int
    provider_type: ExternalProviderType
    label: str
    server_url: str
    site_content_url: Optional[str]
    username: str
    client_id: str
    secret_id: str
    has_secret: bool  # never expose the secret itself
    verify_ssl: bool
    request_timeout_seconds: int
    rest_min_api_version: str
    max_fields: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DatasourceBindingCreate(BaseModel):
    module_type_id: int
    data_entry_type_id: Optional[int] = None
    datasource_luid: str
    label: str


class DatasourceBindingRead(BaseModel):
    id: int
    connection_id: int
    module_type_id: int
    data_entry_type_id: Optional[int]
    datasource_luid: str
    label: str
    is_active: bool
```

- [ ] **Step 2: Verify import**

Run: `cd backend && uv run python -c "from app.schemas.external_connection import ExternalConnectionRead"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/external_connection.py
git commit -m "feat(schemas): external connection + binding DTOs (secret write-only)"
```

---

## Tier 3 — Service + API (PR 3)

### Task 3.1: Service (TDD)

**Files:**

- Create: `backend/app/services/external_connection_service.py`
- Test: `backend/tests/services/test_external_connection_service.py`

**Interfaces:**

- Produces: `ExternalConnectionService(session)` with
  `save_connection(payload: ExternalConnectionCreate) -> ExternalConnection`
  (encrypts `secret_value`),
  `to_read(conn) -> ExternalConnectionRead`,
  `get_decrypted_secret(conn) -> str`,
  `save_binding(connection_id, payload: DatasourceBindingCreate) -> ExternalDatasourceBinding`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.core import crypto
from app.schemas.external_connection import ExternalConnectionCreate
from app.services.external_connection_service import ExternalConnectionService


@pytest.mark.asyncio
async def test_save_encrypts_and_read_hides_secret(db_session, monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    crypto.get_settings.cache_clear()

    service = ExternalConnectionService(db_session)
    conn = await service.save_connection(
        ExternalConnectionCreate(
            label="EPFL Tableau",
            server_url="https://tableau.epfl.ch/",
            site_content_url="co2fp",
            username="svc-calcco2-epfl-api",
            client_id="cid",
            secret_id="sid",
            secret_value="the-real-secret",
        )
    )
    await db_session.commit()

    assert conn.secret_value_encrypted != "the-real-secret"
    assert service.get_decrypted_secret(conn) == "the-real-secret"

    read = service.to_read(conn)
    assert read.has_secret is True
    assert not hasattr(read, "secret_value")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_external_connection_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the service**

```python
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.external_connection import (
    ExternalConnection,
    ExternalDatasourceBinding,
    ExternalProviderType,
)
from app.repositories.external_connection_repo import (
    ExternalConnectionRepository,
    ExternalDatasourceBindingRepository,
)
from app.schemas.external_connection import (
    DatasourceBindingCreate,
    ExternalConnectionCreate,
    ExternalConnectionRead,
)


class ExternalConnectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ExternalConnectionRepository(session)
        self.bindings = ExternalDatasourceBindingRepository(session)

    async def get_by_provider(
        self, provider_type: ExternalProviderType
    ) -> Optional[ExternalConnection]:
        return await self.repo.get_by_provider(provider_type)

    async def save_connection(
        self, payload: ExternalConnectionCreate
    ) -> ExternalConnection:
        """Create or replace the single connection for a provider type."""
        existing = await self.repo.get_by_provider(payload.provider_type)
        target = existing or ExternalConnection(
            provider_type=payload.provider_type,
            secret_value_encrypted="",
            label=payload.label,
            server_url=payload.server_url,
            username=payload.username,
            client_id=payload.client_id,
            secret_id=payload.secret_id,
        )
        target.label = payload.label
        target.server_url = payload.server_url
        target.site_content_url = payload.site_content_url
        target.username = payload.username
        target.client_id = payload.client_id
        target.secret_id = payload.secret_id
        target.secret_value_encrypted = encrypt_secret(payload.secret_value)
        target.verify_ssl = payload.verify_ssl
        target.request_timeout_seconds = payload.request_timeout_seconds
        target.rest_min_api_version = payload.rest_min_api_version
        target.max_fields = payload.max_fields
        return await self.repo.upsert(target)

    def get_decrypted_secret(self, conn: ExternalConnection) -> str:
        return decrypt_secret(conn.secret_value_encrypted)

    def to_read(self, conn: ExternalConnection) -> ExternalConnectionRead:
        if conn.id is None:
            raise ValueError("connection must be persisted before read")
        return ExternalConnectionRead(
            id=conn.id,
            provider_type=conn.provider_type,
            label=conn.label,
            server_url=conn.server_url,
            site_content_url=conn.site_content_url,
            username=conn.username,
            client_id=conn.client_id,
            secret_id=conn.secret_id,
            has_secret=bool(conn.secret_value_encrypted),
            verify_ssl=conn.verify_ssl,
            request_timeout_seconds=conn.request_timeout_seconds,
            rest_min_api_version=conn.rest_min_api_version,
            max_fields=conn.max_fields,
            is_active=conn.is_active,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
        )

    async def save_binding(
        self, connection_id: int, payload: DatasourceBindingCreate
    ) -> ExternalDatasourceBinding:
        existing = await self.bindings.get_active_for_module(
            payload.module_type_id, payload.data_entry_type_id
        )
        target = existing or ExternalDatasourceBinding(
            connection_id=connection_id,
            module_type_id=payload.module_type_id,
            data_entry_type_id=payload.data_entry_type_id,
            datasource_luid=payload.datasource_luid,
            label=payload.label,
        )
        target.connection_id = connection_id
        target.datasource_luid = payload.datasource_luid
        target.label = payload.label
        return await self.bindings.upsert(target)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_external_connection_service.py -v`
Expected: PASS.

- [ ] **Step 5: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/services/external_connection_service.py backend/tests/services/test_external_connection_service.py
git commit -m "feat(service): encryption-aware external connection service"
```

### Task 3.2: Router (TDD)

**Files:**

- Create: `backend/app/api/v1/external_connections.py`
- Modify: the v1 router aggregator (find it next to `api/v1/files.py`; mirror
  how `files.router` is included).
- Test: `backend/tests/api/test_external_connections.py`

**Interfaces:**

- Produces these routes (all under the backoffice permission gate already
  used by `/sync/dispatch` — locate that dependency in `api/v1/data_sync.py`
  and reuse it verbatim):
  - `GET /api/v1/external-connections/{provider_type}` → `ExternalConnectionRead | null`
  - `PUT /api/v1/external-connections` (body `ExternalConnectionCreate`) → `ExternalConnectionRead`
  - `POST /api/v1/external-connections/{connection_id}/datasources` (body `DatasourceBindingCreate`) → `DatasourceBindingRead`
  - `POST /api/v1/external-connections/{provider_type}/test` → `{ "ok": bool, "detail": str }`

- [ ] **Step 1: Write the failing test** (mirror an existing authed API test;
      reuse the auth/client fixtures from `tests/api/test_files.py` or similar):

```python
import pytest


@pytest.mark.asyncio
async def test_put_then_get_connection_hides_secret(authed_client, monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    from app.core import crypto

    crypto.get_settings.cache_clear()

    body = {
        "label": "EPFL Tableau",
        "server_url": "https://tableau.epfl.ch/",
        "site_content_url": "co2fp",
        "username": "svc-calcco2-epfl-api",
        "client_id": "cid",
        "secret_id": "sid",
        "secret_value": "the-real-secret",
    }
    put = await authed_client.put("/api/v1/external-connections", json=body)
    assert put.status_code == 200
    assert "secret_value" not in put.json()
    assert put.json()["has_secret"] is True

    got = await authed_client.get("/api/v1/external-connections/EPFL_TABLEAU")
    assert got.status_code == 200
    assert got.json()["client_id"] == "cid"
    assert "secret_value" not in got.json()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_external_connections.py -v`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Implement the router**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_data_session  # match the existing session dep
from app.models.external_connection import ExternalProviderType
from app.schemas.external_connection import (
    DatasourceBindingCreate,
    DatasourceBindingRead,
    ExternalConnectionCreate,
    ExternalConnectionRead,
)
from app.services.external_connection_service import ExternalConnectionService

# require_backoffice_data_management: reuse the SAME dependency that gates
# POST /sync/dispatch (see app/api/v1/data_sync.py). Deny by default.
from app.api.v1.data_sync import require_backoffice_data_management

router = APIRouter(
    prefix="/external-connections",
    tags=["external-connections"],
    dependencies=[Depends(require_backoffice_data_management)],
)


@router.get("/{provider_type}", response_model=ExternalConnectionRead | None)
async def get_connection(
    provider_type: ExternalProviderType,
    db: AsyncSession = Depends(get_data_session),
):
    service = ExternalConnectionService(db)
    conn = await service.get_by_provider(provider_type)
    return service.to_read(conn) if conn else None


@router.put("", response_model=ExternalConnectionRead)
async def upsert_connection(
    payload: ExternalConnectionCreate,
    db: AsyncSession = Depends(get_data_session),
):
    service = ExternalConnectionService(db)
    conn = await service.save_connection(payload)
    await db.commit()
    return service.to_read(conn)


@router.post(
    "/{connection_id}/datasources", response_model=DatasourceBindingRead
)
async def upsert_binding(
    connection_id: int,
    payload: DatasourceBindingCreate,
    db: AsyncSession = Depends(get_data_session),
):
    service = ExternalConnectionService(db)
    if await service.repo.get_by_id(connection_id) is None:
        raise HTTPException(status_code=404, detail="connection not found")
    binding = await service.save_binding(connection_id, payload)
    await db.commit()
    return DatasourceBindingRead.model_validate(binding, from_attributes=True)


@router.post("/{provider_type}/test")
async def test_connection(
    provider_type: ExternalProviderType,
    db: AsyncSession = Depends(get_data_session),
):
    # Validate by signing a JWT and calling Tableau auth via the base
    # provider's connection-test path (Tier 4 exposes a classmethod).
    from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
        BaseTableauApiProvider,
    )

    ok, detail = await BaseTableauApiProvider.test_connection(db, provider_type)
    return {"ok": ok, "detail": detail}
```

> **Note.** Wire the `/test` route last — it depends on Tier 4's
> `BaseTableauApiProvider.test_connection`. If implementing Tier 3 before
> Tier 4, stub `/test` to `{"ok": false, "detail": "not yet wired"}` and a
> test asserting 200; replace in Tier 4.

- [ ] **Step 4: Register the router** in the v1 aggregator (same place
      `files.router` is included):

```python
from app.api.v1 import external_connections
app.include_router(external_connections.router, prefix="/api/v1")
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_external_connections.py -v`
Expected: PASS.

- [ ] **Step 6: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/api/v1/external_connections.py backend/tests/api/test_external_connections.py <aggregator>
git commit -m "feat(api): external-connections CRUD + datasource bindings"
```

---

## Tier 4 — Base Tableau provider + travel migration (PR 4)

Lift the shared plumbing into a base class and feed the travel provider from
the DB. Behaviour for travel is unchanged; the source of credentials changes.

### Task 4.1: `BaseTableauApiProvider`

**Files:**

- Create: `backend/app/services/data_ingestion/api_providers/base_tableau_api_provider.py`

**Interfaces:**

- Consumes: `ExternalConnectionService`, `ExternalDatasourceBindingRepository`.
- Produces a base class with:
  - class attrs (override per subclass): `PROVIDER_TYPE: ExternalProviderType`,
    `MODULE_TYPE: ModuleTypeEnum`, `DATA_ENTRY_TYPE: DataEntryTypeEnum`,
    `REQUIRED_CAPTIONS: list[str]`.
  - `async _ensure_credentials() -> None` — loads binding + connection once,
    sets `self.server_url`, `self.site_content_url`, `self.username`,
    `self.client_id`, `self.secret_id`, `self.secret_value`,
    `self.datasource_luid`, `self.verify_ssl`, `self.timeout`,
    `self.min_api_version`. Raises `ValueError` with a clear message if no
    connection/binding exists.
  - `async validate_connection() -> bool`, `async fetch_data(filters)`
    (generic: ensure creds → read-metadata → validate `REQUIRED_CAPTIONS` →
    query → rows).
  - moved helpers (verbatim from the travel provider): `_generate_jwt`,
    `_signin_with_jwt`, `_create_session`, `_vds_read_metadata`,
    `_extract_field_captions`, `_build_payload`, `_vds_query_datasource`,
    `_resolve_carbon_report_modules`, `_record_row_error`, `normalize_vds_payload`,
    `to_bool`.
  - `@classmethod async test_connection(db, provider_type) -> tuple[bool, str]`.
  - abstract: `transform_data`, `_build_data_entry(record) -> DataEntry`.

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
        """Load the connection + per-module binding from the DB once."""
        if getattr(self, "_credentials_loaded", False):
            return
        service = ExternalConnectionService(self.data_session)
        conn = await service.get_by_provider(self.PROVIDER_TYPE)
        if conn is None:
            raise ValueError(
                f"No {self.PROVIDER_TYPE.value} connection configured — set "
                "one in the API connect form before importing."
            )
        binding = await service.bindings.get_active_for_module(
            int(self.MODULE_TYPE), self.config.get("data_entry_type_id")
        )
        if binding is None:
            raise ValueError(
                f"No datasource (LUID) bound for module "
                f"{self.MODULE_TYPE.name} — set one in the API connect form."
            )
        self.server_url = conn.server_url
        self.site_content_url = conn.site_content_url
        self.username = conn.username
        self.client_id = conn.client_id
        self.secret_id = conn.secret_id
        self.secret_value = service.get_decrypted_secret(conn)
        self.verify_ssl = conn.verify_ssl
        self.timeout = conn.request_timeout_seconds
        self.min_api_version = conn.rest_min_api_version
        self.datasource_luid = binding.datasource_luid
        self.module_type_id = self.config.get("module_type_id")
        self._credentials_loaded = True
```

`validate_connection` and `fetch_data` call `await self._ensure_credentials()`
first, then run the moved logic (same bodies as today, minus the env reads).

- [ ] **Step 2: Add the classmethod connection test**

```python
    @classmethod
    async def test_connection(
        cls, db: AsyncSession, provider_type: ExternalProviderType
    ) -> tuple[bool, str]:
        service = ExternalConnectionService(db)
        conn = await service.get_by_provider(provider_type)
        if conn is None:
            return False, "No connection configured"
        # Build a throwaway instance bound to the connection's fields and
        # attempt a JWT sign-in (no datasource needed).
        ...  # see Step 3 test for the asserted contract
```

- [ ] **Step 3: Write a unit test** that monkeypatches `_signin_with_jwt` to
      return a token and asserts `validate_connection()` is True after a
      connection row exists; and asserts it raises a clear `ValueError` when no
      connection is configured. File:
      `backend/tests/services/data_ingestion/test_base_tableau_provider.py`.

- [ ] **Step 4: Run the test**

Run: `cd backend && uv run pytest tests/services/data_ingestion/test_base_tableau_provider.py -v`
Expected: PASS.

- [ ] **Step 5: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/services/data_ingestion/api_providers/base_tableau_api_provider.py backend/tests/services/data_ingestion/test_base_tableau_provider.py
git commit -m "feat(ingestion): BaseTableauApiProvider with DB-backed credentials"
```

### Task 4.2: Migrate `ProfessionalTravelApiProvider` onto the base

**Files:**

- Modify: `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py`

- [ ] **Step 1: Reduce the class to its module-specific surface.** It now
      subclasses `BaseTableauApiProvider` and keeps only:
  - class attrs: `PROVIDER_TYPE = ExternalProviderType.EPFL_TABLEAU`,
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
Tableau values, update it to seed an `ExternalConnection` +
`ExternalDatasourceBinding` instead.

- [ ] **Step 3: Remove now-dead env settings** if nothing else references
      them: drop `TABLEAU_DS_FLIGHTS_LUID`, `TABLEAU_CONNECTED_APP_*`,
      `TABLEAU_USERNAME`, etc. from `config.py`. Grep first:

```bash
cd backend && rtk grep "TABLEAU_" app/
```

Keep only settings still referenced. (No backward compat — see memory.)

- [ ] **Step 4: Type-check, lint, commit**

```bash
cd backend && make type-check && make lint
git add backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py backend/app/core/config.py
git commit -m "refactor(ingestion): drive travel provider from DB credentials"
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
> Discover captions with:
>
> ```bash
> # after a connection + headcount binding exist
> curl -s -X POST .../external-connections/EPFL_TABLEAU/test  # sign-in works
> ```
>
> then read-metadata via the base provider in a REPL, and fill the
> `CAPTION_*` constants below from the real metadata.

- [ ] **Step 1: Write the failing transform test** (asserts the mapping
      target, independent of the exact caption strings — parametrize captions as
      constants so the test pins the mapping, not the datasource):

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

from app.models.data_entry import (
    DataEntry,
    DataEntrySourceEnum,
    DataEntryTypeEnum,
)
from app.models.external_connection import ExternalProviderType
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
    BaseTableauApiProvider,
)


class HeadcountMembersApiProvider(BaseTableauApiProvider):
    PROVIDER_TYPE = ExternalProviderType.EPFL_TABLEAU
    MODULE_TYPE = ModuleTypeEnum.headcount
    DATA_ENTRY_TYPE = DataEntryTypeEnum.member

    # Fill these from read-metadata against the headcount LUID.
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
        # (headcount carries no emission override). Build member DataEntry
        # rows via _build_data_entry and bulk_create with source
        # EXTERNAL_INTEGRATION. See professional_travel_api_provider._load_data
        # for the bulk_create call shape.
        ...
```

Implement `ingest` by reusing the travel provider's orchestration shape
(`fetch → transform → _resolve_carbon_report_modules → inject
  carbon_report_module_id → _load_data`). Extract that orchestration into a
shared `BaseTableauApiProvider.ingest` if both providers end up identical
except for `_build_data_entry`; otherwise keep a thin override.

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

Make the dialog save a connection + binding, then dispatch. No JS unit
harness — verify with `make type-check` and `npm run lint`, then a manual
walkthrough.

### Task 6.1: Connections store/client

**Files:**

- Create: `frontend/src/stores/externalConnections.ts`

- [ ] **Step 1:** Add a Pinia store with typed calls mirroring
      `stores/backofficeDataManagement.ts` axios usage:
  - `getConnection(providerType)` → `GET /external-connections/{providerType}`
  - `saveConnection(payload)` → `PUT /external-connections`
  - `saveBinding(connectionId, payload)` → `POST /external-connections/{id}/datasources`
  - `testConnection(providerType)` → `POST /external-connections/{providerType}/test`
    Types should be generated from OpenAPI if the repo uses
    `openapi-typescript` (see plan `217-openapi-typescript-typegen.md`); else
    hand-type to match the Read schemas.

- [ ] **Step 2:** `cd frontend && make type-check && npm run lint`
- [ ] **Step 3:** Commit.

### Task 6.2: Extend the dialog form

**Files:**

- Modify: `frontend/src/components/molecules/data-management/DataEntryDialogContent.vue:151-202`
- Modify: `frontend/src/composables/useDataEntryDialog.ts:33-148`

- [ ] **Step 1:** Add inputs for `site_content_url`, `username`, and
      `datasource_luid` (the LUID for this module) alongside the existing four.
      On open, call `getConnection('EPFL_TABLEAU')`; if present, prefill all
      non-secret fields and leave `secret_value` blank with a "secret already
      set — leave blank to keep" hint.

- [ ] **Step 2:** Replace `connectAndSync()` so it:
  1. `await saveConnection({...})` (omit `secret_value` if left blank on edit —
     requires a backend tweak to allow secret-preserving update; if not in
     scope, require the secret on every save and note it).
  2. `await saveBinding(connectionId, { module_type_id, datasource_luid, label })`.
  3. `await initiateSync('api')` — unchanged dispatch; the provider now loads
     creds from the DB, so `config` stays as today.

- [ ] **Step 3:** Add the new i18n keys
      (`data_management_api_site_content_url`, `..._username`, `..._luid`,
      `..._secret_kept`) to `frontend/src/i18n/backoffice_data_management.ts` and
      every locale.

- [ ] **Step 4:** `cd frontend && make type-check && npm run lint`
- [ ] **Step 5:** Manual walkthrough: open dialog for plane_travel → save
      connection + LUID → "API Connect and Sync" → job succeeds via SSE. Repeat
      for headcount.
- [ ] **Step 6:** Commit.

---

## Self-review checklist (run before opening PRs)

- **Spec coverage:** Goal 1 → Tiers 1-2; Goal 2 → Tier 3; Goal 3 → Tier 4;
  Goal 4 → Tier 5; Goal 5 → Tier 4 base class. Frontend → Tier 6.
- **Secret never leaves the server in plaintext:** confirm no Read schema or
  log statement includes `secret_value` / `secret_value_encrypted`.
- **Fail-closed:** with keys unset, `PUT /external-connections` returns 500
  and no row is written.
- **Type consistency:** `MODULE_TYPE` / `DATA_ENTRY_TYPE` / `PROVIDER_TYPE`
  class attrs match between base and both subclasses; factory key tuple
  matches the registered `(module_type, method, target, entity)`.
- **Docs:** update the data-management docs page in the same PR as Tier 6;
  link this plan from the PRD (done).
