"""Audit helper utilities for extracting metadata from entities.

Provides helper functions to extract audit-relevant information like
handled_ids (affected user provider codes) from various entity types.
"""

from typing import Union

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum

logger = get_logger(__name__)


def extract_handled_ids(
    data_entry: Union[DataEntry, dict], data_entry_type_id: DataEntryTypeEnum
) -> list[str]:
    """
    Extract list of user provider codes affected by this data entry.

    Different data entry types store user identifiers in different fields:
    - Professional travel (trips): traveler_id or sciper
    - Headcount (member/student): sciper or user_provider_code
    - Equipment/Cloud/AI: No user-specific data (returns empty list)

    Args:
        data_entry: DataEntry object or dict containing the data field
        data_entry_type_id: The type of data entry (from DataEntryTypeEnum)

    Returns:
        List of user provider codes (as strings), or empty list if none found
    """
    try:
        # Extract data dict
        if isinstance(data_entry, DataEntry):
            data = data_entry.data
        elif isinstance(data_entry, dict):
            data = data_entry.get("data", data_entry)
        else:
            logger.warning(f"Unexpected data_entry type: {type(data_entry)}")
            return []

        if not data or not isinstance(data, dict):
            return []

        handled_ids = []

        # Professional travel - extract traveler identifier
        if data_entry_type_id == DataEntryTypeEnum.trips:
            # Try multiple field names that might contain the traveler's sciper
            traveler_id = (
                data.get("traveler_id")
                or data.get("sciper")
                or data.get("user_provider_code")
            )
            if traveler_id:
                handled_ids.append(str(traveler_id))

        # Headcount (members and students) - extract sciper if present
        elif data_entry_type_id in [
            DataEntryTypeEnum.member,
            DataEntryTypeEnum.student,
        ]:
            sciper = data.get("sciper") or data.get("user_provider_code")
            if sciper:
                handled_ids.append(str(sciper))

        # Equipment, cloud, AI services typically don't have user-specific data
        # Return empty list for these types

        return handled_ids

    except Exception as e:
        logger.error(f"Error extracting handled_ids: {e}", exc_info=True)
        return []


def extract_handled_ids_from_list(
    data_entries: list[Union[DataEntry, dict]], data_entry_type_id: DataEntryTypeEnum
) -> list[str]:
    """
    Extract unique list of user provider codes from multiple data entries.

    Args:
        data_entries: List of DataEntry objects or dicts
        data_entry_type_id: The type of data entries

    Returns:
        Deduplicated list of user provider codes
    """
    all_ids = []
    for entry in data_entries:
        ids = extract_handled_ids(entry, data_entry_type_id)
        all_ids.extend(ids)

    # Return unique IDs while preserving order
    return list(dict.fromkeys(all_ids))
