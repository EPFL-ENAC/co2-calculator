"""Connector connection + datasource service (#1552).

Encrypts/decrypts the stored secret, enforces the SSRF guard on
``server_url``, and hides the secret from the read schema (only a
``has_secret`` flag is ever returned).
"""

import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.url_safety import validate_external_url
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
    ) -> ConnectorConnection | None:
        return await self.repo.get_by_connector(connector)

    async def save_connection(
        self, connector: ConnectorType, payload: ConnectorConnectionCreate
    ) -> ConnectorConnection:
        """Create or replace the single connection for a connector.

        A blank ``secret_value`` on an existing row keeps the stored secret;
        on a new row it is required.
        """
        validate_external_url(payload.server_url)  # SSRF guard; raises on bad host
        existing = await self.repo.get_by_connector(connector)
        if existing is None and not payload.secret_value:
            raise ValueError("secret_value is required for a new connection")
        target = existing or ConnectorConnection(
            connector=connector,
            label=payload.label,
            server_url=payload.server_url,
            username=payload.username,
            client_id=payload.client_id,
            secret_id=payload.secret_id,
            secret_value_encrypted="",  # nosec B106 - placeholder, overwritten below before persisting
        )
        target.label = payload.label
        target.server_url = payload.server_url
        target.site_content_url = payload.site_content_url
        target.username = payload.username
        target.client_id = payload.client_id
        target.secret_id = payload.secret_id
        if payload.secret_value:
            # Scrypt (n=2**14) is deliberately CPU-heavy — off the event
            # loop, same as get_decrypted_secret below (#2050 Track I3).
            target.secret_value_encrypted = await asyncio.to_thread(
                encrypt_secret, payload.secret_value
            )
        return await self.repo.upsert(target)

    async def get_decrypted_secret(self, conn: ConnectorConnection) -> str:
        return await asyncio.to_thread(decrypt_secret, conn.secret_value_encrypted)

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
            module_type_id=payload.module_type_id,
            data_entry_type_id=payload.data_entry_type_id,
            connection_id=connection_id,
            connector_luid=payload.connector_luid,
            label=payload.label,
        )
        target.connection_id = connection_id
        target.connector_luid = payload.connector_luid
        target.label = payload.label
        return await self.datasources.upsert(target)
