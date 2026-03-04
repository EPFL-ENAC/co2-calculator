## Implementation Plan: Elasticsearch Integration for Audit Table

### Overview

We've implemented pattern 7 as requested, which involves adding a `sync_status` column to track the synchronization state of audit records with Elasticsearch. This approach provides reliability by tracking the sync status of each audit record and allowing for retry mechanisms.

### Implemented Components

1. **Database Schema Changes**
   - Added `sync_status` column to `audit_documents` table with enum values: `pending`, `syncing`, `synced`, `failed`
   - Added `sync_error` column to store error messages for failed sync attempts
   - Added `synced_at` column to track when the record was successfully synced

2. **Model Updates**
   - Updated the `AuditDocument` model to include the new fields
   - Defined the `SyncStatusEnum` enum

3. **Elasticsearch Integration**
   - Created an Elasticsearch client configuration
   - Implemented functions to send audit records to Elasticsearch following the OPDo contract
   - Handle secure connection with the provided certificate

4. **Background Sync Process**
   - Implemented a background task system to handle sync operations
   - Created a periodic task to retry failed syncs
   - Implemented bulk sync for better performance

5. **Configuration**
   - Added Elasticsearch configuration to environment variables

### Detailed Implementation

#### 1. Database Migration

We created a new migration file to add the required columns:

- `sync_status` (ENUM: pending, syncing, synced, failed)
- `sync_error` (TEXT, nullable)
- `synced_at` (TIMESTAMP, nullable)

#### 2. Model Updates

Updated `backend/app/models/audit.py` to include:

- New `SyncStatusEnum` class
- New fields in `AuditDocumentBase` class

#### 3. Elasticsearch Client

Created a new module `backend/app/elasticsearch/client.py` that:

- Configures the Elasticsearch client with the provided connection details
- Handles secure connections using the certificate file
- Implements authentication with the API key
- Transforms audit records to OPDo schema for compliance with ISO 27701

#### 4. Sync Service

Created a new service `backend/app/services/audit_sync_service.py` that:

- Contains methods to sync individual and bulk audit records
- Implements error handling and status updates
- Uses the pattern of updating status to `syncing`, attempting sync, then updating to `synced` or `failed`

#### 5. Background Tasks

Implemented background task processing using FastAPI's BackgroundTasks.

#### 6. Periodic Retry Mechanism

Set up a scheduled task to periodically retry failed syncs.

### OPDo Contract Compliance

We've implemented strict compliance with the OPDo contract for ISO 27701 traceability:

| Field        | Type   | Implementation Details                          |
| ------------ | ------ | ----------------------------------------------- |
| `@timestamp` | date   | Required, formatted with Europe/Zurich timezone |
| `handler_id` | string | Nullable, preserved as-is                       |
| `handled_id` | string | **Required, never null**, comma-separated list  |
| `crudt`      | string | Enum (C/R/U/D) mapped from change_type          |
| `source`     | IP     | Required, validated to be valid IP              |
| `payload`    | string | Required, converted to compact JSON string      |

### Critical Implementation Details

#### 1. handled_id Never Null Enforcement

Implementation ensures handled_id is never null:

```python
def resolve_handled_id(audit_record: dict) -> str:
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
```

#### 2. IP Address Validation

Source field must be a valid IP address:

```python
def validate_ip(ip: str) -> str:
    try:
        ip_address(ip)
        return ip
    except Exception:
        raise ValueError(f"Invalid IP for OPDo: {ip}")
```

#### 3. Payload Stringification

Payload is converted to a compact JSON string:

```python
def stringify_payload(payload) -> str:
    if isinstance(payload, str):
        return payload
    # Convert dict to compact JSON string
    return json.dumps(payload, separators=(",", ":"))
```

#### 4. Complete OPDo Schema Mapper

Production-ready mapper that enforces all OPDo constraints:

```python
def map_to_opdo_schema(audit_record: dict) -> dict:
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
```

### Testing

Comprehensive unit tests have been implemented covering:

1. All utility functions (format_timestamp, validate_ip, resolve_handled_id, stringify_payload, map_to_opdo_schema)
2. All ElasticsearchClient methods (initialization, sync_audit_record, bulk_sync_audit_records, get_audit_record)
3. Edge cases and error conditions
4. OPDo contract compliance validation

All 31 tests are currently passing, confirming our implementation correctly follows the OPDo contract.

# detail mapping

Excellent. Now we’re in **real spec-driven territory**.

This changes a few important things. Let’s lock it down properly.

---

# 📌 OPDo Contract (Based on What You Just Said)

| Field        | Type   | Constraint                                     |
| ------------ | ------ | ---------------------------------------------- |
| `@timestamp` | date   | required                                       |
| `handler_id` | string | nullable                                       |
| `handled_id` | string | **required, never null**, comma-separated list |
| `crudt`      | string | enum (C/R/U/D/…)                               |
| `source`     | IP     | required, must be valid IP                     |
| `payload`    | string | required                                       |

---

# 🚨 Critical Corrections You Must Implement

## 1️⃣ handled_id Must NEVER Be Null

Your current data:

```
"[]"
```

That means no handled ids.

Spec says:

> if handler_id is null → handled_id is unique item and is handler_id (implicit)

So logic becomes:

```python
def resolve_handled_id(audit_record: dict) -> str:
    handled_ids = audit_record.get("handled_ids") or []
    handler_id = audit_record.get("handler_id")

    if handled_ids:
        return ",".join(str(x) for x in handled_ids)

    if handler_id:
        # implicit case
        return str(handler_id)

    raise ValueError("OPDo violation: handled_id cannot be null")
```

You must NEVER send null.

---

## 2️⃣ handler_id Nullable

So:

```python
handler_id = audit_record.get("handler_id")
if handler_id is not None:
    handler_id = str(handler_id)
```

Do NOT auto-fill it unless spec says so.

---

## 3️⃣ source Must Be Valid IP

If you send:

```
"unknown"
```

You are non-compliant.

And yes — for ISO 27701 traceability, unknown IP is useless.

You should validate:

```python
import ipaddress

def validate_ip(ip: str) -> str:
    try:
        ipaddress.ip_address(ip)
        return ip
    except Exception:
        raise ValueError(f"Invalid IP for OPDo: {ip}")
```

If IP is missing → FAIL sync.

Do NOT silently send garbage.

---

## 4️⃣ payload Must Be String

You said:

> payload is a string

So DO NOT send JSON object.

Send either:

### Option A — Condensed JSON string (recommended)

```python
import json

def stringify_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, separators=(",", ":"))
```

That produces compact JSON without spaces.

### Example:

```
{"module_type_id":1,"year":null,...}
```

This is clean and deterministic.

---

# 🧠 Now Let’s Build The Proper Mapper

This is what your production-safe mapper should look like:

```python
import json
import ipaddress
from datetime import datetime
from zoneinfo import ZoneInfo

CRUDT_MAP = {
    "CREATE": "C",
    "READ": "R",
    "UPDATE": "U",
    "DELETE": "D",
}

def format_timestamp(ts_str: str) -> str:
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    dt = dt.replace(tzinfo=ZoneInfo("Europe/Zurich"))
    return dt.isoformat()


def validate_ip(ip: str) -> str:
    ipaddress.ip_address(ip)
    return ip


def resolve_handled_id(audit_record: dict) -> str:
    handled_ids = audit_record.get("handled_ids") or []
    handler_id = audit_record.get("handler_id")

    if handled_ids:
        return ",".join(str(x) for x in handled_ids)

    if handler_id:
        return str(handler_id)

    raise ValueError("OPDo violation: handled_id cannot be null")


def stringify_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, separators=(",", ":"))


def map_to_opdo_schema(audit_record: dict) -> dict:
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
        "payload": stringify_payload(audit_record["route_payload"]),
    }
```

---

# 🎯 Important Architectural Advice

Do NOT:

- Auto-fix bad IPs
- Auto-fill missing handled_id silently
- Allow malformed timestamps

Because:

> If OPDo is ISO 27701 driven, audit logs are legal artifacts.

Fail fast. Log error. Do not index invalid compliance data.

---

# 🔥 What Would Break In Your Current Data

From your sample:

```
"unknown" → invalid IP ❌
"[]" → empty handled_ids ❌
timestamp without timezone ❌
"CREATE" instead of "C" ❌
payload double-encoded JSON ❓
```

So yes — you are currently non-compliant.

---

# 🧪 I Strongly Recommend

Add a unit test like:

```python
def test_opdo_contract_compliance():
    doc = map_to_opdo_schema(sample_record)

    assert doc["@timestamp"]
    assert doc["handled_id"]
    assert doc["crudt"] in ["C","R","U","D"]
```

---

1. IPv6 allowed a priori (we should validate IP)
2. Is localhost (127.0.0.1) a priori ?
3. a priori never happen ? (10.x, 192.168.x)
4. no timezone required example of valid: “2024-10-10T11:34:05+02:00"
