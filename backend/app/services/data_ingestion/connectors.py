"""Hardcoded connector registry (#1552).

A new integration is one more entry here plus a provider subclass (Tier 3+).
The form renders ``form_fields`` for the chosen connector.
"""

from dataclasses import dataclass

from app.models.connector import ConnectorType


@dataclass(frozen=True)
class ConnectorSpec:
    connector: ConnectorType
    label: str
    form_fields: tuple[str, ...]


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
