"""Connector registry, connection, and datasource endpoints (#1552).

Gated by ``backoffice.configuration``/``edit`` — the same permission
``sync_module_factors`` requires for global data-sync (deny by default).
Secrets are never returned: routes only ever emit the Read schemas, whose
``has_secret`` flag replaces the raw value.
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.security import require_permission
from app.models.audit import AuditChangeTypeEnum
from app.models.connector import ConnectorType
from app.models.user import User
from app.schemas.connector import (
    ConnectorConnectionCreate,
    ConnectorConnectionRead,
    ConnectorDatasourceCreate,
    ConnectorDatasourceRead,
    ConnectorSpecRead,
)
from app.services.audit_service import AuditDocumentService
from app.services.connector_service import ConnectorConnectionService
from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
    BaseTableauApiProvider,
)
from app.services.data_ingestion.api_providers.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
)
from app.services.data_ingestion.connectors import list_connectors

router = APIRouter()

# Maps a connector to the provider whose ``test_connection`` classmethod
# runs the live sign-in probe. One entry per registered connector.
_TEST_PROVIDERS: dict[ConnectorType, type[BaseTableauApiProvider]] = {
    ConnectorType.EPFL_TABLEAU: ProfessionalTravelApiProvider,
}

# Deny by default: same gate as sync_module_factors (data_sync.py:1005-1007).
_require_edit = require_permission("backoffice.configuration", "edit")

# Minimal in-process per-user cooldown for /test (no rate-limiter dependency
# exists in this app). Module-level so it survives across requests.
TEST_COOLDOWN_SECONDS = 30.0
_last_test_at: dict[Optional[int], float] = {}


@router.get("", response_model=list[ConnectorSpecRead])
async def get_connectors(
    current_user: User = Depends(_require_edit),
) -> list[ConnectorSpecRead]:
    return [
        ConnectorSpecRead(
            connector=s.connector, label=s.label, form_fields=list(s.form_fields)
        )
        for s in list_connectors()
    ]


@router.get("/{connector}/connection", response_model=Optional[ConnectorConnectionRead])
async def get_connection(
    connector: ConnectorType,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_edit),
) -> Optional[ConnectorConnectionRead]:
    service = ConnectorConnectionService(db)
    conn = await service.get_by_connector(connector)
    return service.to_read(conn) if conn else None


@router.put("/{connector}/connection", response_model=ConnectorConnectionRead)
async def upsert_connection(
    connector: ConnectorType,
    payload: ConnectorConnectionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_edit),
) -> ConnectorConnectionRead:
    service = ConnectorConnectionService(db)
    try:
        conn = await service.save_connection(connector, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    read = service.to_read(conn)

    audit_service = AuditDocumentService(db)
    await audit_service.create_version(
        entity_type="ConnectorConnection",
        entity_id=conn.id,  # type: ignore[arg-type]
        data_snapshot=read.model_dump(mode="json"),
        change_type=AuditChangeTypeEnum.UPDATE,
        changed_by=current_user.id,
        change_reason=f"Connection saved for {connector.value}",
        handler_id=current_user.institutional_id,
        handled_ids=[],
        ip_address=request.client.host if request.client else None,
        route_path=request.url.path,
    )
    await db.commit()
    return read


@router.post("/{connector}/datasources", response_model=ConnectorDatasourceRead)
async def upsert_datasource(
    connector: ConnectorType,
    payload: ConnectorDatasourceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_edit),
) -> ConnectorDatasourceRead:
    service = ConnectorConnectionService(db)
    conn = await service.get_by_connector(connector)
    if conn is None or conn.id is None:
        raise HTTPException(status_code=404, detail="connection not found")
    ds = await service.save_datasource(conn.id, payload)
    read = ConnectorDatasourceRead.model_validate(ds, from_attributes=True)

    audit_service = AuditDocumentService(db)
    await audit_service.create_version(
        entity_type="ConnectorDatasource",
        entity_id=ds.id,  # type: ignore[arg-type]
        data_snapshot=read.model_dump(mode="json"),
        change_type=AuditChangeTypeEnum.UPDATE,
        changed_by=current_user.id,
        change_reason=f"Datasource saved for {connector.value}",
        handler_id=current_user.institutional_id,
        handled_ids=[],
        ip_address=request.client.host if request.client else None,
        route_path=request.url.path,
    )
    await db.commit()
    return read


@router.post("/{connector}/test")
async def test_connection(
    connector: ConnectorType,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_edit),
) -> dict:
    """Trigger a live connection test.

    Enforces a per-user cooldown so the outbound call is rate-limited, then
    runs the provider's JWT sign-in probe. ``detail`` is always a generic
    string — never a raw exception, stack trace, or provider response body
    (A06/A10).

    The test itself is audited (PRD): who + when + connector + the boolean
    outcome — never the secret, never a raw error. Rate-limited (429) calls
    raise before this point, so they leave no audit row.
    """
    now = time.monotonic()
    last = _last_test_at.get(current_user.id)
    if last is not None and now - last < TEST_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=429, detail="test already in progress; try again shortly"
        )
    _last_test_at[current_user.id] = now
    provider_cls = _TEST_PROVIDERS.get(connector)
    if provider_cls is None:
        return {"ok": False, "detail": "connector not supported"}
    ok, detail = await provider_cls.test_connection(db, connector)

    # Audit the test attempt. Snapshot carries only the connector + boolean
    # outcome; no secret material, no raw error string is ever persisted.
    service = ConnectorConnectionService(db)
    conn = await service.get_by_connector(connector)
    if conn is not None and conn.id is not None:
        audit_service = AuditDocumentService(db)
        await audit_service.create_version(
            entity_type="ConnectorConnection",
            entity_id=conn.id,
            data_snapshot={"connector": connector.value, "test_ok": ok},
            change_type=AuditChangeTypeEnum.UPDATE,
            changed_by=current_user.id,
            change_reason=(
                f"Connection test for {connector.value}: {'ok' if ok else 'failed'}"
            ),
            handler_id=current_user.institutional_id,
            handled_ids=[],
            ip_address=request.client.host if request.client else None,
            route_path=request.url.path,
        )
        await db.commit()
    return {"ok": ok, "detail": detail}
