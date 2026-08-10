"""Repositories for connector connections and datasources (#1552)."""

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
    ) -> ConnectorConnection | None:
        result = await self.session.exec(
            select(ConnectorConnection).where(
                col(ConnectorConnection.connector) == connector
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
        self, module_type_id: int, data_entry_type_id: int | None = None
    ) -> ConnectorDatasource | None:
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

    async def upsert(self, ds: ConnectorDatasource) -> ConnectorDatasource:
        self.session.add(ds)
        await self.session.flush()
        await self.session.refresh(ds)
        return ds
