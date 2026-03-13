# Plan: Travel — Link Traveler Selection to Headcount (Issue #372)

## Context

Travel entries currently store `traveler_name` as a free-text string and `traveler_id`
as an optional integer (intended for SCIPER). There is no enforced link to the Headcount
module, so a travel entry can reference a person who is not in the unit's headcount, and
names can drift (typos, inconsistent spelling).

This plan makes the traveler picker in the travel form a controlled dropdown that only
shows headcount members who have a `user_institutional_id` (SCIPER). The `traveler_name`
displayed in the travel table is then resolved from the headcount record instead of being
stored as a duplicate string.

**Prerequisite**: Issue #518 (SCIPER uniqueness validation + label) must be merged first,
because it guarantees that `user_institutional_id` is unique per `carbon_report_module_id`.

---

## Data model decisions

| Field in travel `data` JSON | Stores                                                                        |
| --------------------------- | ----------------------------------------------------------------------------- |
| `traveler_id`               | SCIPER as integer (= `int(user_institutional_id)` from headcount)             |
| `traveler_name`             | **Dropped from create/update payloads**; resolved at read time from headcount |

Using SCIPER (not the headcount `DataEntry.id`) is more stable: if headcount data is
re-uploaded from CSV the DataEntry IDs change but SCIPER stays constant.

`traveler_name` is kept in the response DTO for backward compatibility with the table, but
it is no longer written by the client — the backend resolves it from headcount on every
read.

---

## Part 1 — Backend

### 1.1 New endpoint: list headcount members (lightweight)

**File**: `backend/app/api/v1/carbon_report_module.py`

Add a new route **before** the generic `/{unit_id}/{year}/{module_id}` route to avoid path
collision:

```
GET /modules/{unit_id}/{year}/headcount/members
```

Returns the list of headcount members for the given unit/year that have a
`user_institutional_id`. This is used exclusively to populate the travel traveler
dropdown.

```python
class HeadcountMemberDropdownItem(BaseModel):
    sciper: int           # = int(user_institutional_id)
    name: str

@router.get(
    "/{unit_id}/{year}/headcount/members",
    response_model=list[HeadcountMemberDropdownItem],
)
async def list_headcount_members_for_dropdown(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HeadcountMemberDropdownItem]:
    """Return headcount members that have a SCIPER, for use in travel traveler dropdown."""
    await _check_module_permission(current_user, "headcount", "view")
    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum.headcount,
        db=db,
    )
    rows = (await db.execute(
        select(DataEntry.data).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id,
            DataEntry.data_entry_type_id == DataEntryTypeEnum.member.value,
            DataEntry.data["user_institutional_id"].as_string() != None,
        ).order_by(DataEntry.data["name"].as_string())
    )).scalars().all()
    result = []
    for data in rows:
        uid = data.get("user_institutional_id")
        name = data.get("name", "")
        if uid:
            result.append(HeadcountMemberDropdownItem(sciper=int(uid), name=name))
    return result
```

**Important**: declare this route before `/{unit_id}/{year}/{module_id}` (same pattern
used for building-rooms, see MEMORY.md).

---

### 1.2 Travel create — validate `traveler_id` against headcount

**File**: `backend/app/api/v1/carbon_report_module.py` — `create()` endpoint

After `validated_data = handler.validate_create(create_payload)`, if the entry is a
travel type and `traveler_id` is provided, verify the SCIPER exists in the headcount for
the same unit/year:

```python
if data_entry_type in (DataEntryTypeEnum.plane, DataEntryTypeEnum.train):
    sciper = validated_data.model_dump().get("traveler_id")
    if sciper is not None:
        headcount_crm_id = await get_carbon_report_id(
            unit_id=unit_id,
            year=year,
            module_type_id=ModuleTypeEnum.headcount,
            db=db,
        )
        member = (await db.execute(
            select(DataEntry).where(
                DataEntry.carbon_report_module_id == headcount_crm_id,
                DataEntry.data_entry_type_id == DataEntryTypeEnum.member.value,
                DataEntry.data["user_institutional_id"].as_string() == str(sciper),
            ).limit(1)
        )).scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Traveler SCIPER not found in this unit's headcount for the given year.",
            )
        # Resolve and inject traveler_name from headcount
        validated_data_dict = validated_data.model_dump()
        validated_data_dict["traveler_name"] = member.data.get("name", "")
        # rebuild validated_data from dict so DataEntryService receives it
        validated_data = type(validated_data).model_validate(validated_data_dict)
```

This ensures:

- Only headcount members can be linked.
- `traveler_name` is always sourced from headcount — no client-supplied value accepted.

---

### 1.3 Travel update — same validation, refresh name

Apply the same check in the `update()` endpoint when `traveler_id` changes. If the client
sends a new `traveler_id`, re-validate and re-resolve `traveler_name`.

---

### 1.4 Travel schema changes

**File**: `backend/app/modules/professional_travel/schemas.py`

In `ProfessionalTravelPlaneHandlerCreate` and `ProfessionalTravelTrainHandlerCreate`:

- Keep `traveler_id: Optional[int] = None` — this is the SCIPER sent by the client.
- Make `traveler_name: Optional[str] = None` (was `str`, required) — it will be
  overwritten by the backend from headcount.

In `ProfessionalTravelPlaneHandlerResponse` and `ProfessionalTravelTrainHandlerResponse`:

- Keep `traveler_name: Optional[str] = None` for display in tables.
- Add `traveler_sciper: Optional[int] = None` as an alias read from `traveler_id` for
  frontend clarity (optional, can keep as `traveler_id`).

---

### 1.5 CSV ingestion — map SCIPER to headcount name

**File**: `backend/app/services/data_ingestion/csv_providers/professional_travel_csv_provider.py`

The CSV already accepts a `sciper` column → `traveler_id`. Extend the ingestion to:

1. After parsing a row, query headcount for the same unit/year to resolve the name.
2. If SCIPER is found in headcount → populate `traveler_name` from headcount.
3. If SCIPER is not found → skip the row and emit a warning (do not silently accept
   an unlinked traveler).

```python
# After mapping sciper -> traveler_id:
if traveler_id:
    member = await _resolve_headcount_member(session, carbon_report_module_id_headcount, traveler_id)
    if member is None:
        logger.warning(f"Row skipped: SCIPER {traveler_id} not in headcount for unit {unit_id}/{year}")
        continue
    transformed_row["traveler_name"] = member.data["name"]
```

Add a helper `_resolve_headcount_member(session, headcount_crm_id, sciper)` in the same
file.

---

## Part 2 — Frontend

### 2.1 New API call: fetch headcount members dropdown

**File**: `frontend/src/api/modules.ts` (or wherever API calls live)

```typescript
export const getHeadcountMembers = (unitId: number, year: number) =>
  api.get<HeadcountMemberDropdownItem[]>(
    `/modules/${unitId}/${year}/headcount/members`,
  );

export interface HeadcountMemberDropdownItem {
  sciper: number;
  name: string;
}
```

---

### 2.2 Change `traveler_name` field to SCIPER-linked autocomplete

**File**: `frontend/src/constant/module-config/professional-travel.ts`

Replace the `traveler_name` text field with a new field type `headcount-member-select`:

```typescript
{
  id: 'traveler_id',
  labelKey: `${MODULES.ProfessionalTravel}-field-traveler`,
  type: 'headcount-member-select',   // new field type
  required: true,
  sortable: true,
  ratio: '1/1',
  editableInline: false,
},
```

The `traveler_name` field (currently in the table) becomes read-only and is populated
from the backend response — no config change needed for table display since the response
still returns `traveler_name`.

---

### 2.3 New component: `HeadcountMemberSelect.vue`

**File**: `frontend/src/components/modules/HeadcountMemberSelect.vue`

A Quasar `QSelect` with:

- Options loaded from `getHeadcountMembers(unitId, year)` on mount.
- Option label: `"${name} (${sciper})"`.
- Option value: the `sciper` integer.
- Emits `update:modelValue` with the selected `sciper`.
- Emits `name-resolved` with the resolved `name` (so the form can display it in the
  table preview without an extra API call).
- Shows a warning banner if the headcount is empty: _"No headcount members with SCIPER
  found. Add members to Headcount first."_
- `use-input` + `filter` for search-as-you-type on large lists.

Wire `traveler_id` ← selected sciper. The form does **not** send `traveler_name`; the
backend resolves it.

---

### 2.4 Wire new component into the generic field renderer

**File**: `frontend/src/components/modules/ModuleFieldInput.vue` (or equivalent)

Add a branch for `type === 'headcount-member-select'` that renders `HeadcountMemberSelect`
and passes `unitId` + `year` as props.

---

### 2.5 Table column: display resolved `traveler_name`

No change needed in the table config — the API response still returns `traveler_name`
(now backend-resolved from headcount). The column labeled "Traveler" continues to show
the name.

Optionally add a `traveler_id` (SCIPER) column in a tooltip or secondary line for
power users.

---

### 2.6 i18n additions

**File**: `frontend/src/i18n/professional_travel.ts`

```typescript
[`${MODULES.ProfessionalTravel}-field-traveler-empty-headcount`]: {
  en: 'No headcount members with SCIPER found. Add members in the Headcount module first.',
  fr: 'Aucun membre du personnel avec SCIPER trouvé. Ajoutez des membres dans le module Effectifs.',
},
```

---

## Part 3 — Edge cases

| Scenario                                               | Handling                                                                                             |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Headcount module has no entries                        | Dropdown shows empty list + warning banner                                                           |
| Headcount module not yet created for unit/year         | `GET /headcount/members` returns 404 → frontend catches it, shows "Create headcount first" message   |
| Travel entry created via API/CSV without `traveler_id` | `traveler_name` is required if `traveler_id` absent — kept for backward compatibility but deprecated |
| Headcount member deleted after travel entry linked     | `traveler_name` stored in `data` JSON preserves last resolved name; no re-resolution on read (KISS)  |
| SCIPER changed in headcount (edge case)                | Travel retains old resolved name in `data`; name stays consistent                                    |

---

## Critical files

| File                                                                                    | Change                                                                                                      |
| --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py`                                            | New `GET /{unit_id}/{year}/headcount/members` endpoint; validate `traveler_id` in `create()` and `update()` |
| `backend/app/modules/professional_travel/schemas.py`                                    | `traveler_name` optional on create; add response note                                                       |
| `backend/app/services/data_ingestion/csv_providers/professional_travel_csv_provider.py` | Validate SCIPER against headcount, resolve name                                                             |
| `frontend/src/api/modules.ts`                                                           | `getHeadcountMembers()` function                                                                            |
| `frontend/src/components/modules/HeadcountMemberSelect.vue`                             | **New** — dropdown component                                                                                |
| `frontend/src/components/modules/ModuleFieldInput.vue`                                  | Add branch for `headcount-member-select` type                                                               |
| `frontend/src/constant/module-config/professional-travel.ts`                            | Replace `traveler_name` text field with `traveler_id` + `headcount-member-select` type                      |
| `frontend/src/i18n/professional_travel.ts`                                              | Add empty-headcount warning key                                                                             |

---

## Verification

1. **Headcount populated**: Travel form shows a dropdown with all SCIPER members from headcount. Selecting one saves `traveler_id` (SCIPER). The table shows the resolved name.
2. **Headcount empty**: Travel form shows the warning banner instead of the dropdown.
3. **Invalid SCIPER via API**: `POST /modules/{unit_id}/{year}/professional-travel/plane` with `traveler_id` not in headcount → HTTP 422 `"Traveler SCIPER not found in this unit's headcount for the given year."`.
4. **CSV upload**: Row with a valid SCIPER that exists in headcount → imported successfully, `traveler_name` resolved automatically. Row with unknown SCIPER → row skipped, warning logged.
5. **Name consistency**: Updating a headcount member's name does not affect existing travel entries (stored name frozen in `data` JSON). New travel entries after the headcount update pick up the new name.
