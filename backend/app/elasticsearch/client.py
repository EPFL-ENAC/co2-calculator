"""Elasticsearch client for audit log synchronization following OPDo contract.

Handles secure connection to Elasticsearch using provided certificate and API key.
Transforms audit records to OPDo schema for compliance with ISO 27701.
"""

import json
import logging
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    AuthenticationException,
    ConnectionError,
    NotFoundError,
)

from app.core.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

settings = get_settings()

# Elasticsearch configuration
ELASTICSEARCH_HOSTS = settings.ELASTICSEARCH_HOSTS
ELASTICSEARCH_INDEX = settings.ELASTICSEARCH_INDEX
ELASTICSEARCH_ID = settings.ELASTICSEARCH_ID
ELASTICSEARCH_API_KEY = settings.ELASTICSEARCH_API_KEY

# Certificate path - use environment variable or default location
CERT_PATH = settings.ELASTICSEARCH_CA_CERT

# CRUDT mapping
CRUDT_MAP = {
    "CREATE": "C",
    "READ": "R",
    "UPDATE": "U",
    "DELETE": "D",
}


def format_timestamp(timestamp_input: str | datetime) -> str:
    """
    Format timestamp to ISO format with timezone.

    Args:
        timestamp_input: Timestamp string in format "YYYY-MM-DD HH:MM:SS.f"
        or datetime object

    Returns:
        str: ISO formatted timestamp with timezone

    Raises:
        ValueError: If timestamp string cannot be parsed
    """
    # Handle case where input is already a datetime object
    if isinstance(timestamp_input, datetime):
        dt = timestamp_input
    else:
        # Handle different timestamp formats
        try:
            # Try parsing with microseconds first
            dt = datetime.strptime(timestamp_input, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            # If that fails, try without microseconds
            try:
                dt = datetime.strptime(timestamp_input, "%Y-%m-%d %H:%M:%S")
            except ValueError as e:
                raise ValueError(
                    f"Unable to parse timestamp '{timestamp_input}'. "
                    f"Expected format 'YYYY-MM-DD HH:MM:SS[.f]'"
                ) from e

    # Add timezone info (Europe/Zurich as specified in the spec)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Zurich"))
    else:
        # If timezone info already exists, convert to Europe/Zurich
        dt = dt.astimezone(ZoneInfo("Europe/Zurich"))

    return dt.isoformat()


def validate_ip(ip: str) -> str:
    """
    Validate that the IP address is valid.

    Args:
        ip: IP address string

    Returns:
        str: Validated IP address

    Raises:
        ValueError: If IP address is invalid
    """
    # Handle None or empty IP
    if not ip:
        raise ValueError("Invalid IP for OPDo: IP address is empty or None")

    # Handle "unknown" IP addresses by using a placeholder
    if ip.lower() == "unknown":
        # never replace the following code by '0.0.0' or '::' as
        # these are reserved IPs and can cause issues with some libraries
        raise ValueError("IP address cannot be 'unknown'")

    try:
        ip_address(ip)
        return ip
    except Exception:
        raise ValueError(f"Invalid IP for OPDo: {ip}")


def resolve_handled_id(audit_record: dict) -> str:
    """
    Resolve handled_id from handled_ids or handler_id.

    Args:
        audit_record: Audit record dictionary

    Returns:
        str: Comma-separated handled IDs string

    Raises:
        ValueError: If neither handled_ids nor handler_id is available
    """
    handled_ids = audit_record.get("handled_ids") or []
    handler_id = audit_record.get("handler_id")

    # If we have handled_ids, join them
    if handled_ids:
        return ",".join(str(x) for x in handled_ids)

    # If we have handler_id, use it as the implicit handled_id
    if handler_id:
        return str(handler_id)

    # Neither handled_ids nor handler_id available - this violates OPDo contract
    raise ValueError("OPDo violation: handled_id cannot be null")


def stringify_payload(payload) -> str:
    """
    Convert payload to string representation.

    Args:
        payload: Payload data (can be string or dict)

    Returns:
        str: String representation of payload
    """
    if isinstance(payload, str):
        return payload
    # Convert dict to compact JSON string
    return json.dumps(payload, separators=(",", ":"))


def map_to_opdo_schema(audit_record: dict) -> dict:
    """
    Map audit record to OPDo schema for compliance.

    Args:
        audit_record: Audit record dictionary

    Returns:
        dict: Mapped record following OPDo schema

    Raises:
        ValueError: If audit record doesn't comply with OPDo contract
    """
    # Create composite payload with all required fields
    composite_payload = {
        "route_path": audit_record.get("route_path"),
        "route_payload": audit_record.get("route_payload"),
        "change_reason": audit_record.get("change_reason"),
        "entity_type": audit_record.get("entity_type"),
        "entity_id": audit_record.get("entity_id"),
    }

    return {
        "@timestamp": format_timestamp(audit_record["changed_at"]),
        "handler_id": (
            str(audit_record["handler_id"])
            if audit_record.get("handler_id") is not None
            else None
        ),
        "handled_id": resolve_handled_id(audit_record),
        "crudt": CRUDT_MAP[audit_record["change_type"]],
        "source": validate_ip(audit_record["ip_address"]),
        "payload": stringify_payload(composite_payload),
    }


class ElasticsearchClient:
    """Client for Elasticsearch operations with audit logs following OPDo contract."""

    def __init__(self, es_client=None):
        """Initialize Elasticsearch client with secure connection.

        Args:
            es_client: Optional Elasticsearch client instance for testing
        """
        self.client = es_client
        if es_client is None:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize the Elasticsearch client with secure connection."""
        try:
            # Verify certificate file exists
            if not Path(CERT_PATH).exists():
                raise FileNotFoundError(
                    f"Elasticsearch CA certificate not found at {CERT_PATH}"
                )

            # Split the comma-separated hosts into a list
            hosts_list = [
                host.strip() for host in ELASTICSEARCH_HOSTS.split(",") if host.strip()
            ]

            # Create Elasticsearch client with SSL certificate verification
            self.client = Elasticsearch(
                hosts=hosts_list,
                api_key=(ELASTICSEARCH_ID, ELASTICSEARCH_API_KEY),
                ca_certs=CERT_PATH,
                verify_certs=True,
                ssl_show_warn=False,
                request_timeout=30,
                max_retries=3,
                retry_on_timeout=True,
            )

            # Test the connection
            self.client.info()
            logger.info("Successfully connected to Elasticsearch")

        except FileNotFoundError as e:
            logger.error(f"Certificate file not found: {e}")
            raise
        except ConnectionError as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            raise
        except AuthenticationException as e:
            logger.error(f"Authentication failed with Elasticsearch: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing Elasticsearch client: {e}")
            raise

    def sync_audit_record(self, audit_record: dict) -> bool:
        """
        Sync a single audit record to Elasticsearch following OPDo contract.

        Args:
            audit_record: Dictionary containing audit record data

        Returns:
            bool: True if sync was successful, False otherwise
        """
        if not self.client:
            logger.error("Elasticsearch client not initialized")
            return False

        try:
            # Extract the document ID from the audit record
            doc_id = str(audit_record.get("id"))

            # Transform audit record to OPDo schema
            opdo_document = map_to_opdo_schema(audit_record)

            # Index the document in Elasticsearch with op_type=create for data streams
            self.client.index(
                index=ELASTICSEARCH_INDEX,
                id=doc_id,
                document=opdo_document,
                op_type="create",
            )

            logger.info(f"Successfully synced audit record {doc_id} to Elasticsearch")
            return True

        except ValueError as e:
            logger.error(
                f"OPDo contract violation for audit record "
                f"{audit_record.get('id')}: {e}"
            )
            return False
        except Exception as e:
            # Check if this is a version conflict (document already exists)
            if "version_conflict_engine_exception" in str(e):
                logger.info(
                    f"Audit record {audit_record.get('id')} already exists "
                    f"in Elasticsearch treating as successful sync"
                )
                return True
            logger.error(
                f"Failed to sync audit record {audit_record.get('id')} "
                f"to Elasticsearch: {e}"
            )
            return False

    def bulk_sync_audit_records(self, audit_records: list[dict]) -> dict:
        """
        Bulk sync multiple audit records to Elasticsearch following OPDo contract.

        Args:
            audit_records: List of audit record dictionaries

        Returns:
            dict: Statistics about the bulk operation
        """
        if not self.client:
            logger.error("Elasticsearch client not initialized")
            return {"success": 0, "failed": 0, "errors": [], "conflicts": []}

        try:
            # Prepare actions for bulk indexing
            actions = []
            validation_errors = []

            for record in audit_records:
                try:
                    # Transform audit record to OPDo schema
                    opdo_document = map_to_opdo_schema(record)

                    actions.append(
                        {
                            "_op_type": "create",
                            "_index": ELASTICSEARCH_INDEX,
                            "_id": str(record.get("id")),
                            "_source": opdo_document,
                        }
                    )
                except ValueError as e:
                    validation_errors.append(
                        {
                            "id": record.get("id"),
                            "error": str(e),
                        }
                    )
                    logger.error(
                        f"OPDo contract violation for audit record "
                        f"{record.get('id')}: {e}"
                    )
                except Exception as e:
                    validation_errors.append(
                        {
                            "id": record.get("id"),
                            "error": str(e),
                        }
                    )
                    logger.error(
                        f"Error processing audit record {record.get('id')}: {e}"
                    )

            # If no valid actions, return early
            if not actions:
                logger.info("No valid audit records to sync after validation")
                return {
                    "success": 0,
                    "failed": len(validation_errors),
                    "errors": validation_errors,
                    "conflicts": [],
                }

            # Perform bulk indexing
            from elasticsearch.helpers import bulk

            success_count, failed_items = bulk(
                self.client, actions, raise_on_error=False, raise_on_exception=False
            )

            # Extract errors and conflicts
            errors = validation_errors[:]  # Start with validation errors
            conflicts = []  # List to store version conflicts
            failed_count = len(validation_errors)

            # Handle the case where failed_items might be an integer or a list
            if isinstance(failed_items, int):
                failed_count += failed_items
            elif hasattr(failed_items, "__iter__"):
                for item in failed_items:
                    if "create" in item:
                        error_reason = item["create"].get("error", {}).get("reason", "")
                        doc_id = item["create"].get("_id")

                        error_type = item["create"].get("error", {}).get("type", "")

                        # Check if this is a version conflict
                        is_version_conflict = (
                            "version_conflict_engine_exception" in error_reason
                            or "version_conflict_engine_exception" in error_type
                        )

                        if is_version_conflict:
                            conflicts.append(
                                {
                                    "id": doc_id,
                                    "error": error_reason,
                                }
                            )
                        else:
                            errors.append(
                                {
                                    "id": doc_id,
                                    "error": error_reason,
                                }
                            )

                # Calculate failed_count: non-conflict errors
                # (including validation errors)
                failed_count = len(errors)
            # else case is when failed_items is None, which means no failures

            logger.info(
                f"Bulk sync completed: {success_count} successful, "
                f"{len(conflicts)} conflicts, {failed_count} failed"
            )

            return {
                "success": success_count,
                "failed": failed_count,
                "errors": errors,
                "conflicts": conflicts,
            }

        except Exception as e:
            logger.error(f"Failed to bulk sync audit records to Elasticsearch: {e}")
            return {
                "success": 0,
                "failed": len(audit_records),
                "errors": [str(e)],
                "conflicts": [],
            }

    def get_audit_record(self, doc_id: str) -> Optional[dict]:
        """
        Retrieve an audit record from Elasticsearch.

        Args:
            doc_id: ID of the audit record

        Returns:
            dict or None: The audit record if found, None otherwise
        """
        if not self.client:
            logger.error("Elasticsearch client not initialized")
            return None

        try:
            response = self.client.get(index=ELASTICSEARCH_INDEX, id=doc_id)
            return response["_source"]
        except NotFoundError:
            logger.warning(f"Audit record {doc_id} not found in Elasticsearch")
            return None
        except Exception as e:
            logger.error(
                f"Failed to retrieve audit record {doc_id} from Elasticsearch: {e}"
            )
            return None
