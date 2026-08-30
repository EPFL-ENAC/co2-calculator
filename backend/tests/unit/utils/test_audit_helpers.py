"""Unit tests for audit_helpers, headcount_role_category, and request_context."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

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


def test_extract_ip_address_ignores_forged_forwarded_for():
    """Regression (#2530): the OpenShift router *appends* to X-Forwarded-For,
    so a client sending its own header owns the first element. The audit trail
    must record the peer uvicorn saw, not a value the caller picked.
    """
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
    request.client = MagicMock()
    request.client.host = "9.8.7.6"
    assert extract_ip_address(request) == "9.8.7.6"


def test_extract_ip_address_from_client():
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "9.8.7.6"
    assert extract_ip_address(request) == "9.8.7.6"


def test_extract_ip_address_returns_unknown_when_no_client():
    """No peer means no attributable IP — a forged header must not fill the gap."""
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "1.2.3.4"}
    request.client = None
    assert extract_ip_address(request) == "unknown"


def test_extract_ip_address_returns_unknown_when_client_host_empty():
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    request.client.host = None
    assert extract_ip_address(request) == "unknown"


# ── extract_ip_address behind the real proxy chain (#2530) ───────────────────
#
# The tests above stub `request.client`. These run the same helper behind
# uvicorn's actual ProxyHeadersMiddleware, configured with the CIDRs the
# deployment actually uses, so they pin what the audit trail records in
# production rather than what a MagicMock returns.

# openshift-app-config, overlays/{dev,stage,prod}: 10.20.0.0/16 is the pod
# overlay subnet (which includes the haproxy routers), 10.98.42.0/24 the AVI
# load balancers.
DEPLOYED_FORWARDED_ALLOW_IPS = "10.20.0.0/16,10.98.42.0/24"


async def _ip_recorded_for(peer: str, forwarded_for: str, *, trusted: str) -> str:
    """The IP the audit trail records for one request through the proxy chain.

    ``peer`` is the TCP peer uvicorn sees (the router pod); ``forwarded_for``
    is the X-Forwarded-For header as it arrives, leftmost entry first.
    """
    resolved: dict[str, Request] = {}

    async def app(scope, receive, send):
        resolved["request"] = Request(scope)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "client": (peer, 51234),
        "headers": [(b"x-forwarded-for", forwarded_for.encode())],
    }
    await ProxyHeadersMiddleware(app, trusted_hosts=trusted)(scope, None, None)
    return extract_ip_address(resolved["request"])


@pytest.mark.asyncio
async def test_audit_ip_is_the_real_user_not_the_forged_forwarded_for():
    """Regression (#2530): an internet client prepending its own
    X-Forwarded-For must not change the recorded IP.

    Chain as deployed: the client's forged entry, then the address AVI
    observed (the real client), then AVI's own address appended by HAProxy.
    uvicorn walks in from the right past every trusted hop and stops at the
    first untrusted one — the user.
    """
    recorded = await _ip_recorded_for(
        peer="10.20.1.5",
        forwarded_for="1.2.3.4, 203.0.113.9, 10.98.42.7",
        trusted=DEPLOYED_FORWARDED_ALLOW_IPS,
    )
    assert recorded == "203.0.113.9"


@pytest.mark.asyncio
async def test_a_caller_inside_the_pod_subnet_can_still_choose_its_own_ip():
    """Characterization, not an endorsement — this is why `internal.py`
    cannot authenticate on `request.client.host` alone (#2530).

    The deployed allowlist trusts 10.20.0.0/16, the *whole* pod overlay
    subnet. A caller inside it is a trusted proxy: every entry in the chain
    is trusted, uvicorn finds no untrusted hop, and falls back to the
    leftmost — which the caller wrote.
    """
    recorded = await _ip_recorded_for(
        peer="10.20.1.5",
        forwarded_for="10.20.4.4, 10.20.9.9",
        trusted=DEPLOYED_FORWARDED_ALLOW_IPS,
    )
    assert recorded == "10.20.4.4"


@pytest.mark.asyncio
async def test_trusting_every_proxy_makes_the_audit_ip_forgeable():
    """Why `assert_proxy_trust_settings` refuses to boot on '*': it skips the
    walk entirely and takes the client-chosen first element.
    """
    recorded = await _ip_recorded_for(
        peer="10.20.1.5",
        forwarded_for="1.2.3.4, 203.0.113.9, 10.98.42.7",
        trusted="*",
    )
    assert recorded == "1.2.3.4"


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
