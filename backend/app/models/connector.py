"""Connector connection + datasource models (API-connect credentials, #1552)."""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class ConnectorType(str, Enum):
    EPFL_TABLEAU = "EPFL_TABLEAU"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ConnectorConnection(SQLModel, table=True):
    """One connection per connector (where + who + connected-app creds).

    ``secret_value`` is stored encrypted (Fernet token); every other column
    is an identifier entered in the form.
    """

    __tablename__ = "connector_connections"

    id: int | None = Field(default=None, primary_key=True, index=True)
    connector: ConnectorType = Field(
        sa_column=Column(
            SAEnum(ConnectorType, name="connector_type_enum", native_enum=True),
            nullable=False,
            unique=True,
        ),
    )
    label: str = Field(nullable=False)
    server_url: str = Field(nullable=False)
    site_content_url: str | None = Field(default=None, nullable=True)
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
        sa_column=Column(
            DateTime(timezone=True),
            default=_utcnow,
            onupdate=_utcnow,
            nullable=False,
        ),
    )


class ConnectorDatasource(SQLModel, table=True):
    """One datasource (LUID) for one module, owned by a connection."""

    __tablename__ = "connector_datasources"

    id: int | None = Field(default=None, primary_key=True, index=True)
    connection_id: int = Field(
        foreign_key="connector_connections.id", nullable=False, index=True
    )
    module_type_id: int = Field(nullable=False, index=True)
    data_entry_type_id: int | None = Field(default=None, nullable=True)
    connector_luid: str = Field(nullable=False)
    label: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            DateTime(timezone=True),
            default=_utcnow,
            onupdate=_utcnow,
            nullable=False,
        ),
    )
