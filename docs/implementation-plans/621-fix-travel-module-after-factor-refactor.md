# Fix Travel Module After Factor Refactor (#621)

## Context

Commit `ddd7eb50` (refactor(factors): simplify factor seeding and handling, merged 2026-03-11)
changed the professional travel module backend schemas from **location ID-based** to
**IATA/name-based** identifiers. The frontend was not updated to match, causing two broken
behaviours:

1. **From/to dropdown selects the right location but submits wrong payload** — the backend
   no longer accepts `origin_location_id` / `destination_location_id`; it now expects
   `origin_iata` / `destination_iata` (plane) or `origin_name` / `destination_name` (train).

2. **Distance displayed in the form is fine** (the `/locations/calculate-distance` endpoint
   still accepts IDs and still exists), but the saved entry has `distance_km = null` and
   `kg_co2eq = null` because `pre_compute()` reads `origin_iata`/`destination_iata` from
   `data_entry.data`, finds nothing, and returns early.

A third related issue — replacing `traveler_name` with `user_institutional_id` and a headcount
member dropdown — **is already being handled in Ben's branch**:
`feat/372-travel-refactor-travel-to-new-db-scheme-selection-of-travelers-names-link-to-headcount`.
That work should NOT be duplicated here; coordinate merge order instead.

---

## Root Cause Analysis

### Backend changes in `ddd7eb50` (what changed)

| File                             | Change                                                                                                                                                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `professional_travel/schemas.py` | `ProfessionalTravelPlaneHandlerCreate`: removed `traveler_name`, `traveler_id`, `origin_location_id`, `destination_location_id`; added `origin_iata`, `destination_iata`, `user_institutional_id`, `cabin_class`, `note` |
| `professional_travel/schemas.py` | `ProfessionalTravelTrainHandlerCreate`: same pattern with `origin_name` / `destination_name`                                                                                                                             |
| `professional_travel/schemas.py` | `pre_compute()` now calls `get_location_by_iata(origin_iata)` / `get_location_by_name(origin_name)` instead of `get_location_by_id(origin_location_id)`                                                                  |
| `professional_travel/schemas.py` | Train `resolve_computations()`: changed factor lookup from `kind=country_code` to `context={"country_code": country_code}` + `fallbacks={"country_code": "RoW"}`                                                         |

### Backend — what is now stale/broken

Because new entries store `origin_iata` / `destination_iata` (not `origin_location_id` /
`destination_location_id`) in `data_entry.data`, the existing Location JOIN in
`data_entry_repo.py` always resolves `origin_loc` / `dest_loc` to `None` for new-style
entries. Two consequences:

1. **JOIN condition is dead**: `DataEntry.data["origin_location_id"].as_integer()` is `null`
   for all new entries, so `OriginLocation` / `DestLocation` outer-joins return no rows.

2. **Response DTO is inconsistent**: `ProfessionalTravelPlaneHandlerResponse` still declares
   `origin_location_id: int` and `destination_location_id: int` but these fields no longer
   exist in new entries' `data` JSON — causing Pydantic validation errors or None values.

### Frontend — what was NOT updated

| File                                     | Still-broken behaviour                                                                                                                                       |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `CO2DestinationInput.vue` (line 360–365) | Emits `from-location-selected` / `to-location-selected` with `{ id, name, latitude, longitude }` — **missing `iata_code`** needed for plane payload          |
| `ModuleForm.vue` (line 156–157)          | DirectionInput bound to `form.origin` / `form.destination` (hardcoded); these fields are not sent in the payload and not populated from rowData in edit mode |
| `ModuleForm.vue` (line 886)              | `handleFromLocationSelected` stores `form.origin_location_id = location.id` only — never sets `form.origin_iata` / `form.origin_name`                        |
| `ModuleForm.vue` (line 812–816)          | `buildPayload()` appends `origin_location_id` / `destination_location_id` — rejected by backend                                                              |
| `ModuleForm.vue` (line 600–609)          | Direction-input init sets `form.origin_location_id` / `form.destination_location_id` — orphan state                                                          |
| `professional-travel.ts` (line 80–86)    | `traveler_name` still shown as editable text input; `user_institutional_id` missing from form fields ← **Ben's PR**                                          |

---

## What to Fix (scope: this branch / PR)

### 0. Backend — remove stale Location JOIN and fix response DTOs

**File**: `backend/app/repositories/data_entry_repo.py`

Remove the `OriginLocation` / `DestLocation` aliased joins from the travel query (lines
295–348). These joined on `DataEntry.data["origin_location_id"]` which is no longer stored.
Also remove the corresponding unpack in the result loop and the `origin`/`destination` name
injection:

```python
# REMOVE these lines from entities list for travel:
entities.extend([MemberEntry, OriginLocation, DestLocation, DataEntryEmission])
# becomes:
entities.extend([MemberEntry, DataEntryEmission])

# REMOVE the two .join() blocks for OriginLocation and DestLocation

# REMOVE from result unpack:
member_entry, origin_loc, dest_loc, emission = ...
# becomes:
member_entry, emission = ...

# REMOVE the name-injection patches:
**({"origin": origin_loc.name} if origin_loc else {}),
**({"destination": dest_loc.name} if dest_loc else {}),
```

**File**: `backend/app/modules/professional_travel/schemas.py`

Update response DTOs to reflect the new storage format — replace `origin_location_id` /
`destination_location_id` with the IATA / name fields:

```python
class ProfessionalTravelPlaneHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    user_institutional_id: int
    origin_iata: str           # was: origin_location_id: int
    destination_iata: str      # was: destination_location_id: int
    cabin_class: Optional[str] = None
    ...

class ProfessionalTravelTrainHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    user_institutional_id: int
    origin_name: str           # was: origin_location_id: int
    destination_name: str      # was: destination_location_id: int
    ...
```

---

### 1. `CO2DestinationInput.vue` — emit full location identifiers

**File**: `frontend/src/components/atoms/CO2DestinationInput.vue`

Extend the `LocationSelection` interface and both `handleFromSelection` /
`handleToSelection` to include `iata_code` and `country_code`:

```ts
// line ~179
interface LocationSelection {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  iata_code: string | null; // ADD
  country_code: string | null; // ADD
}
```

In `handleFromSelection` and `handleToSelection`, pass the extra fields in the emitted
object (the `value` variable is already typed as `Location` which has both fields):

```ts
emit("from-location-selected", {
  id: value.id,
  name: value.name,
  latitude: value.latitude,
  longitude: value.longitude,
  iata_code: value.iata_code ?? null, // ADD
  country_code: value.country_code ?? null, // ADD
});
```

---

### 2. `ModuleForm.vue` — store identifiers and fix payload

**File**: `frontend/src/components/organisms/module/ModuleForm.vue`

#### 2a. Store iata_code / name on location selection (lines 878–924)

```ts
async function handleFromLocationSelected(location: {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  iata_code: string | null; // ADD
  country_code: string | null; // ADD
}) {
  const travelMode = getTravelMode();
  if (!travelMode) return;

  // Keep ID for the distance preview call
  form.origin_location_id = location.id;

  // Store the correct identifier for the backend payload
  if (travelMode === "plane") {
    form.origin_iata = location.iata_code ?? location.name; // fallback to name
  } else {
    form.origin_name = location.name;
  }

  // ... existing distance calculation logic unchanged ...
}
```

Same pattern for `handleToLocationSelected`:

```ts
if (travelMode === "plane") {
  form.destination_iata = location.iata_code ?? location.name;
} else {
  form.destination_name = location.name;
}
```

#### 2b. Swap also swaps the identifiers (line 926)

```ts
async function handleSwapLocations() {
  const travelMode = getTravelMode();
  // ... existing ID swap ...
  if (travelMode === "plane") {
    [form.origin_iata, form.destination_iata] = [
      form.destination_iata,
      form.origin_iata,
    ];
  } else {
    [form.origin_name, form.destination_name] = [
      form.destination_name,
      form.origin_name,
    ];
  }
  // ... existing distance calc ...
}
```

#### 2c. Fix `buildPayload()` (lines 779–819)

Remove the block that appends `origin_location_id` / `destination_location_id` (lines
810–816). Instead, the correct fields (`origin_iata`, `destination_iata`, `origin_name`,
`destination_name`) will be in `form` and will be picked up automatically by the existing
`Object.keys(form)` loop — as long as they are NOT in `excludedFields`.

Make sure these field ids are NOT in `excludedFields`:

```ts
const excludedFields = [
  "origin_location_data",
  "destination_location_data",
  "origin",
  "destination",
  "origin_location_id", // ADD to exclude — no longer sent
  "destination_location_id", // ADD to exclude — no longer sent
  "round_trip",
  "distance_km",
  "kg_co2eq",
];
```

#### 2d. Init direction-input fields (line 600–609)

Add initialization for the new identifier fields:

```ts
case 'direction-input':
  if (!form.origin) form.origin = '';
  if (!form.destination) form.destination = '';
  // Location IDs — only for distance preview, NOT sent to backend
  if (!props.rowData) {
    form.origin_location_id = undefined;
    form.destination_location_id = undefined;
    // New identifier fields
    form.origin_iata = undefined;
    form.destination_iata = undefined;
    form.origin_name = undefined;
    form.destination_name = undefined;
  }
  break;
```

Same additions in `reset()` (line 849–856):

```ts
form.origin_iata = undefined;
form.destination_iata = undefined;
form.origin_name = undefined;
form.destination_name = undefined;
```

#### 2e. Edit mode — pre-populate display fields (line 581–587)

When `init()` is called with `props.rowData`, it copies all rowData keys into `form` and
returns early. `form.origin` / `form.destination` (display text for the DirectionInput) are
not in rowData, so the widget shows empty when editing an existing row.

After the rowData copy loop, add:

```ts
if (props.rowData) {
  Object.keys(props.rowData).forEach((key) => {
    form[key] = props.rowData[key];
    errors[key] = null;
  });
  // Pre-populate DirectionInput display text from the new identifier fields
  form.origin =
    (props.rowData.origin_iata as string) ||
    (props.rowData.origin_name as string) ||
    "";
  form.destination =
    (props.rowData.destination_iata as string) ||
    (props.rowData.destination_name as string) ||
    "";
  return;
}
```

---

### 3. What Ben's branch handles (DO NOT duplicate)

`feat/372-travel-refactor-travel-to-new-db-scheme-selection-of-travelers-names-link-to-headcount`
already contains:

- `HeadcountMemberSelect.vue` — dropdown that fetches headcount members for the unit/year
- `professional-travel.ts` — replaces `traveler_name` (text) with `user_institutional_id`
  (type `headcount-member-select`), hides `traveler_name` in form, shows it read-only in table
- `ModuleForm.vue` — renders `headcount-member-select` type
- Backend CSV provider + data entry repo changes for `user_institutional_id` validation

**Merge order recommendation**: merge this fix branch first (location identifiers), then
merge Ben's branch on top, or vice-versa with a rebase — both touch `ModuleForm.vue` and
`professional-travel.ts` so expect conflicts; they are in non-overlapping sections.

---

## Testing Checklist

### Manual tests

- [ ] Plane form: type "Zurich" in From → autocomplete shows results
- [ ] Plane form: select "Zurich Airport (ZRH)" → `origin_iata = "ZRH"` stored
- [ ] Plane form: select destination → distance preview shows in km
- [ ] Plane form: submit → entry saved with non-null `distance_km` and `kg_co2eq`
- [ ] Plane form: swap button → From/To and their IATA codes both swap
- [ ] Train form: type "Basel" → autocomplete shows stations
- [ ] Train form: select station → `origin_name` stored
- [ ] Train form: submit → entry saved with non-null `distance_km` and `kg_co2eq`
- [ ] Train fallback: international route (e.g. Paris→Brussels) → uses `RoW` factor

### Edit mode

- [ ] Open an existing plane entry → From / To show the airport names (not empty)
- [ ] Open an existing train entry → From / To show the station names (not empty)

### Unit / integration tests

- [ ] `CO2DestinationInput.vue`: `from-location-selected` event includes `iata_code`
- [ ] `ModuleForm.vue`: `buildPayload()` for plane includes `origin_iata`, NOT `origin_location_id`
- [ ] `ModuleForm.vue`: `buildPayload()` for train includes `origin_name`, NOT `origin_location_id`
- [ ] Backend: `ProfessionalTravelPlaneHandlerCreate` validates that `origin_iata` is present
- [ ] Backend: `pre_compute()` returns non-empty context when valid IATA codes are provided
- [ ] Backend: GET submodule endpoint returns `origin_iata` in response (not `origin_location_id`)

---

## Files to Change

| File                                                                     | Change type                                                                        |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `backend/app/repositories/data_entry_repo.py`                            | Remove OriginLocation/DestLocation JOIN; fix result unpack                         |
| `backend/app/modules/professional_travel/schemas.py`                     | Fix response DTOs: replace `origin_location_id` with `origin_iata` / `origin_name` |
| `frontend/src/components/atoms/CO2DestinationInput.vue`                  | Add `iata_code`, `country_code` to emitted event                                   |
| `frontend/src/components/organisms/module/ModuleForm.vue`                | Store iata/name, fix payload, fix init/reset, fix edit pre-populate                |
| ~~`frontend/src/constant/module-config/professional-travel.ts`~~         | Ben's PR                                                                           |
| ~~`frontend/src/components/organisms/module/HeadcountMemberSelect.vue`~~ | Ben's PR                                                                           |

---

## Known Remaining Issues (out of scope here)

- `ProfessionalTravelPlaneHandlerUpdate` and `ProfessionalTravelTrainHandlerUpdate`
  (lines 151–160 in `schemas.py`) still have commented-out old fields and still reference
  `origin_location_id` — the update/edit flow is not yet wired to new identifiers.
- `class_adjustement` typo in factor fields (`schemas.py` line ~328) — existing TODO comment.
