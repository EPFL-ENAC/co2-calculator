# Plan: Headcount `user_institutional_id` — Uniqueness Validation + Institution Label

## Context

The headcount module stores a `user_institutional_id` (SCIPER at EPFL) per member entry.
Two issues exist:

1. **No uniqueness check**: the same SCIPER can be entered twice in the same unit's carbon report, causing duplicate data.
2. **Generic label**: the field shows "Institutional ID" but EPFL calls it "SCIPER". The label should be institution-configurable by a dev.

Scope: uniqueness is **per `carbon_report_module_id`** (same unit + year). The same SCIPER across different units/years is allowed (by design).

---

## Part 1 — Backend: Uniqueness Validation on Create

### Files to modify

**`backend/app/api/v1/carbon_report_module.py`** — `create()` endpoint (lines ~407–434)

After `validated_data = handler.validate_create(create_payload)` and before `DataEntryService(db).create(...)`, insert a uniqueness check for headcount members:

```python
from sqlmodel import select, col

# After validated_data is built:
if (
    data_entry_type == DataEntryTypeEnum.member
    and validated_data.model_dump().get("user_institutional_id")
):
    uid = validated_data.model_dump()["user_institutional_id"]
    duplicate = (await db.execute(
        select(DataEntry).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id,
            DataEntry.data_entry_type_id == DataEntryTypeEnum.member.value,
            DataEntry.data["user_institutional_id"].as_string() == uid,
        ).limit(1)
    )).scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This user's institutional ID (Sciper) already exists.",
        )
```

This reuses the existing `DataEntry.data["field"].as_string()` JSON query pattern already used in filter/sort maps (e.g., `schemas.py:150`).

### Why here, not in the schema/service

The check requires a DB query and `carbon_report_module_id` context. The API endpoint is the right layer — it already owns both. No new service method needed.

---

## Part 2 — Frontend: Institution-Configurable Label

### New file: `frontend/src/constant/institution.ts`

```typescript
/**
 * Institution-specific display configuration.
 *
 * Configuring for your institution:
 *   - Set INSTITUTIONAL_ID_LABEL to the term your institution uses
 *     for the internal user identifier stored in headcount.
 *
 * Examples:
 *   EPFL  → 'SCIPER'
 *   Other → 'Institutional ID'
 *
 * This value is used in headcount form labels, table column headers,
 * and error messages across the application.
 */
export const INSTITUTIONAL_ID_LABEL = "SCIPER"; // EPFL default
```

### Modify: `frontend/src/i18n/headcount.ts`

Import the constant and replace the static string:

### Why here, and how it is wired through the service/repository

### Modify: `frontend/src/i18n/headcount.ts`

Import the constant and replace the static string:

```typescript
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';

// Replace the existing label (line 92-95):
[`${MODULES.Headcount}-member-form-field-user-institutional-id-label`]: {
en: INSTITUTIONAL_ID_LABEL,
fr: INSTITUTIONAL_ID_LABEL,
},
```

## Verification

1. **Backend**: POST to `POST /modules/{unit_id}/{year}/headcount/member` twice with the same `user_institutional_id` → second call returns HTTP 422 with `"This user's institutional ID (Sciper) already exists."`.
2. **Backend**: Same `user_institutional_id` in a different unit → succeeds (different `carbon_report_module_id`).
3. **Frontend**: Headcount member form field label shows "SCIPER" instead of "Institutional ID".

# Plan: Headcount `user_institutional_id` — Uniqueness Validation + Institution Label

## Context

The headcount module stores a `user_institutional_id` (SCIPER at EPFL) per member entry.
Two issues exist:

1. **No uniqueness check**: the same SCIPER can be entered twice in the same unit's carbon report, causing duplicate data.
2. **Generic label**: the field shows "Institutional ID" but EPFL calls it "SCIPER". The label should be institution-configurable by a dev.

Scope: uniqueness is **per `carbon_report_module_id`** (same unit + year). The same SCIPER across different units/years is allowed (by design).

---

## Part 1 — Backend: Uniqueness Validation on Create

### Files to modify

**`backend/app/api/v1/carbon_report_module.py`** — `create()` endpoint (lines ~407–434)

After `validated_data = handler.validate_create(create_payload)` and before `DataEntryService(db).create(...)`, insert a uniqueness check for headcount members:

```python
from sqlmodel import select, col

# After validated_data is built:
if (
    data_entry_type == DataEntryTypeEnum.member
    and validated_data.model_dump().get("user_institutional_id")
):
    uid = validated_data.model_dump()["user_institutional_id"]
    duplicate = (await db.execute(
        select(DataEntry).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id,
            DataEntry.data_entry_type_id == DataEntryTypeEnum.member.value,
            DataEntry.data["user_institutional_id"].as_string() == uid,
        ).limit(1)
    )).scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This user's institutional ID already exists.",
        )
```

This reuses the existing `DataEntry.data["field"].as_string()` JSON query pattern already used in filter/sort maps (e.g., `schemas.py:150`).

### Why here, not in the schema/service

The check requires a DB query and `carbon_report_module_id` context. The API endpoint is the right layer — it already owns both. No new service method needed.

---

## Part 2 — Frontend: Institution-Configurable Label

### New file: `frontend/src/constant/institution.ts`

```typescript
/**
 * Institution-specific display configuration.
 *
 * Configuring for your institution:
 *   - Set INSTITUTIONAL_ID_LABEL to the term your institution uses
 *     for the internal user identifier stored in headcount.
 *
 * Examples:
 *   EPFL  → 'SCIPER'
 *   Other → 'Institutional ID'
 *
 * This value is used in headcount form labels, table column headers,
 * and error messages across the application.
 */
export const INSTITUTIONAL_ID_LABEL = "SCIPER"; // EPFL default
```

### Modify: `frontend/src/i18n/headcount.ts`

Import the constant and replace the static string:

```typescript
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institution';

// Replace the existing label (line 92-95):
[`${MODULES.Headcount}-member-form-field-user-institutional-id-label`]: {
en: INSTITUTIONAL_ID_LABEL,
fr: INSTITUTIONAL_ID_LABEL,
},
```

Since "SCIPER" is an acronym with no translation, both `en` and `fr` use the same constant.

---

## Critical Files

| File                                         | Change                                    |
| -------------------------------------------- | ----------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py` | Add SCIPER uniqueness check in `create()` |
| `frontend/src/constant/institution.ts`       | **New** — institution config constant     |
| `frontend/src/i18n/headcount.ts`             | Import and use `INSTITUTIONAL_ID_LABEL`   |

---

## Verification

1. **Backend**: POST to `/modules/{unit_id}/{year}/headcount/member` twice with the same `user_institutional_id` → second call returns HTTP 422 with `"This user's institutional ID already exists."`.
2. **Backend**: Same `user_institutional_id` in a different unit → succeeds (different `carbon_report_module_id`).
3. **Frontend**: Headcount member form field label shows "SCIPER" instead of "Institutional ID".
4. **Label change**: Change `INSTITUTIONAL_ID_LABEL` in `institution.ts` to `'Institutional ID'` → label updates everywhere without touching i18n or components.
   import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institution';

// Replace the existing label (line 92-95):
[`${MODULES.Headcount}-member-form-field-user-institutional-id-label`]: {
en: INSTITUTIONAL_ID_LABEL,
fr: INSTITUTIONAL_ID_LABEL,
},

```

Since "SCIPER" is an acronym with no translation, both `en` and `fr` use the same constant.

---

## Critical Files

| File                                         | Change                                    |
| -------------------------------------------- | ----------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py` | Add SCIPER uniqueness check in `create()` |
| `frontend/src/constant/institution.ts`       | **New** — institution config constant     |
| `frontend/src/i18n/headcount.ts`             | Import and use `INSTITUTIONAL_ID_LABEL`   |

---

## Verification

1. **Backend**: POST to `POST /modules/{unit_id}/{year}/headcount/member` twice with the same `user_institutional_id` → second call returns HTTP 422 with `"This user's  **unit_instituional_ID_display_text** already exists."`.
2. **Backend**: Same `user_institutional_id` in a different unit → succeeds (different `carbon_report_module_id`).
3. **Frontend**: Headcount member form field label shows "SCIPER" instead of "Institutional ID".
4. **Label change**: Change `INSTITUTIONAL_ID_LABEL` in `institution.ts` to `'Institutional ID'` → label updates everywhere without touching i18n or components.
```
