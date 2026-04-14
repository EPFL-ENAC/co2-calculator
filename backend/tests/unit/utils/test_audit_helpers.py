"""Unit tests for audit_helpers, headcount_role_category, and request_context."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.utils.audit_helpers import extract_handled_ids, extract_handled_ids_from_list
from app.utils.headcount_role_category import ROLE_CATEGORY_MAPPING, get_function_role
from app.utils.request_context import (
    extract_ip_address,
    extract_route_info,
    extract_route_payload,
)

# ── headcount_role_category ───────────────────────────────────────────────────


def test_get_function_role_known_role():
    assert get_function_role("Professeur") == "professor"


def test_get_function_role_unknown_returns_other():
    assert get_function_role("Unknown Role XYZ") == "other"


def test_get_function_role_student():
    assert get_function_role("Étudiant-e") == "student"


def test_get_function_role_technical():
    assert get_function_role("Technicien") == "technical_administrative_staff"


def test_role_category_mapping_is_populated():
    assert len(ROLE_CATEGORY_MAPPING) > 0
    assert "Professeur" in ROLE_CATEGORY_MAPPING


# ── extract_ip_address ────────────────────────────────────────────────────────


def test_extract_ip_address_from_forwarded_for():
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
    request.client = None
    assert extract_ip_address(request) == "1.2.3.4"


def test_extract_ip_address_from_client():
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "9.8.7.6"
    assert extract_ip_address(request) == "9.8.7.6"


def test_extract_ip_address_returns_unknown_when_no_client():
    request = MagicMock()
    request.headers = {}
    request.client = None
    assert extract_ip_address(request) == "unknown"


def test_extract_ip_address_returns_unknown_when_client_host_empty():
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    request.client.host = None
    assert extract_ip_address(request) == "unknown"


# ── extract_route_payload ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_route_payload_returns_none_for_get_no_params():
    request = MagicMock()
    request.query_params = {}
    request.method = "GET"
    assert await extract_route_payload(request) is None


@pytest.mark.asyncio
async def test_extract_route_payload_includes_query_params():
    request = MagicMock()
    request.query_params = {"year": "2024"}
    request.method = "GET"
    result = await extract_route_payload(request)
    assert result == {"query": {"year": "2024"}}


@pytest.mark.asyncio
async def test_extract_route_payload_includes_json_body():
    request = MagicMock()
    request.query_params = {}
    request.method = "POST"
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(return_value={"key": "value"})
    result = await extract_route_payload(request)
    assert result == {"body": {"key": "value"}}


@pytest.mark.asyncio
async def test_extract_route_payload_skips_body_for_get():
    request = MagicMock()
    request.query_params = {}
    request.method = "GET"
    result = await extract_route_payload(request)
    assert result is None


@pytest.mark.asyncio
async def test_extract_route_payload_handles_json_parse_error():
    request = MagicMock()
    request.query_params = {}
    request.method = "POST"
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(side_effect=Exception("parse error"))
    result = await extract_route_payload(request)
    assert result is None


# ── extract_route_info ────────────────────────────────────────────────────────


def test_extract_route_info_returns_path_and_none_params():
    request = MagicMock()
    request.url.path = "/api/v1/modules/1/2024"
    request.query_params = {}
    path, params = extract_route_info(request)
    assert path == "/api/v1/modules/1/2024"
    assert params is None


def test_extract_route_info_returns_query_params():
    request = MagicMock()
    request.url.path = "/api/v1/modules/1/2024"
    request.query_params = {"page": "1"}
    path, params = extract_route_info(request)
    assert path == "/api/v1/modules/1/2024"
    assert params == {"page": "1"}


# ── extract_handled_ids ───────────────────────────────────────────────────────


def test_extract_handled_ids_plane_with_institutional_id():
    entry = {"user_institutional_id": "12345"}
    result = extract_handled_ids(entry, DataEntryTypeEnum.plane)
    assert result == ["12345"]


def test_extract_handled_ids_train_with_sciper():
    entry = {"sciper": "67890"}
    result = extract_handled_ids(entry, DataEntryTypeEnum.train)
    assert result == ["67890"]


def test_extract_handled_ids_member_with_sciper():
    entry = {"sciper": "11111"}
    result = extract_handled_ids(entry, DataEntryTypeEnum.member)
    assert result == ["11111"]


def test_extract_handled_ids_student_with_provider_code():
    entry = {"user_provider_code": "22222"}
    result = extract_handled_ids(entry, DataEntryTypeEnum.student)
    assert result == ["22222"]


def test_extract_handled_ids_returns_empty_for_equipment():
    entry = {"device": "laptop"}
    result = extract_handled_ids(entry, DataEntryTypeEnum.it_equipment)
    assert result == []


def test_extract_handled_ids_returns_empty_when_no_identifier():
    entry = {}
    result = extract_handled_ids(entry, DataEntryTypeEnum.plane)
    assert result == []


def test_extract_handled_ids_from_data_entry_object():
    data_entry = MagicMock(spec=DataEntry)
    data_entry.data = {"user_institutional_id": "99999"}
    result = extract_handled_ids(data_entry, DataEntryTypeEnum.plane)
    assert result == ["99999"]


def test_extract_handled_ids_pydantic_model():
    entry = MagicMock()
    entry.model_dump.return_value = {"user_institutional_id": "55555"}
    result = extract_handled_ids(entry, DataEntryTypeEnum.plane)
    assert result == ["55555"]


def test_extract_handled_ids_returns_empty_on_exception():
    result = extract_handled_ids(None, DataEntryTypeEnum.plane)
    assert result == []


# ── extract_handled_ids_from_list ─────────────────────────────────────────────


def test_extract_handled_ids_from_list_deduplicates():
    entries = [
        {"user_institutional_id": "111"},
        {"user_institutional_id": "111"},
        {"user_institutional_id": "222"},
    ]
    result = extract_handled_ids_from_list(entries, DataEntryTypeEnum.plane)
    assert result == ["111", "222"]


def test_extract_handled_ids_from_list_empty():
    assert extract_handled_ids_from_list([], DataEntryTypeEnum.plane) == []
