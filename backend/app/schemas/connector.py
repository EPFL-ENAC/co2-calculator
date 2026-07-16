"""Connector connection + datasource DTOs (#1552).

Secrets are write-only: ``ConnectorConnectionCreate`` accepts ``secret_value``
in the clear (encrypted before persistence by the service layer) and doubles
as the update payload — a blank/omitted value keeps the stored secret;
``ConnectorConnectionRead`` never returns it, only a ``has_secret`` flag.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.connector import ConnectorType


class ConnectorSpecRead(BaseModel):
    connector: ConnectorType
    label: str
    form_fields: list[str]


class ConnectorConnectionCreate(BaseModel):
    label: str = Field(max_length=255)
    server_url: str = Field(max_length=2048)
    site_content_url: Optional[str] = Field(default=None, max_length=255)
    username: str = Field(max_length=255)
    client_id: str = Field(max_length=255)
    secret_id: str = Field(max_length=255)
    # required on create; blank keeps on update
    secret_value: Optional[str] = Field(default=None, max_length=4096)


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
    connector_luid: str = Field(max_length=255)
    label: str = Field(max_length=255)


class ConnectorDatasourceRead(BaseModel):
    id: int
    connection_id: int
    module_type_id: int
    data_entry_type_id: Optional[int]
    connector_luid: str
    label: str
    is_active: bool
