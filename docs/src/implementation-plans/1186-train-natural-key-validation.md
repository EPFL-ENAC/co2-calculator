---
status: delivered
issue: 1186
last_updated: 2026-08-20
summary: "Closes the remaining natural_key validation gap #1183 left open: train API creates and CSV not_found stations no longer persist silently with zero emissions — both now fail hard at ingest time."
---

# 1186 — Train natural_key validation: close the remaining gap

## 1. Where this picks up

#1186 originally reported that `ProfessionalTravelTrainHandlerCreate` left
`origin_natural_key`/`destination_natural_key` fully optional, so a payload
missing them persisted silently — `pre_compute` just logs a WARNING and
returns `{}` (zero emissions, no visible error).

**#1183 shipped since and closed part of this** (trainline-eu station seed,
required `{role}_country_code`): CSV rows missing `country_code`, or with an
ambiguous name+country match, now get a hard row error. `origin_name` /
`destination_name` / `*_country_code` became required `str` on the DTO.

**Still open, verified against the current code** (see the issue comment
posted 2026-08-20):

1. `origin_natural_key`/`destination_natural_key` remain `str | None = None`
   on the create DTO — required by the CSV timing constraint (`validate_create`
   runs before `enrich_csv_row` resolves them), but nothing fills the gap on
   the **API path**, which never calls `enrich_csv_row` at all.
2. `ModuleForm.vue`'s `direction-input` validation checks only the free-text
   display value (`form.origin`/`form.destination`), never the resolved
   identifier (`origin_iata` for plane, `origin_natural_key` for train) — a
   user who types a name without picking an autocomplete suggestion submits
   successfully today.
3. #1183 deliberately kept CSV `not_found` (0 station matches) as
   warn-and-persist, mirroring plane's unknown-IATA behavior. Per this
   issue's direction ("no silent fallback"), that's being superseded for
   train: `not_found` becomes a hard row error too, same as `country_code`-
   missing and ambiguous already are.

**Explicitly out of scope:** plane's matching unknown-IATA silent-zero-
emission path (same shape, different issue — flagged to the user, not fixed
here) and the train **update** DTO (`ProfessionalTravelTrainHandlerUpdate`,
still optional natural_key) — the frontend fix below closes the UI hole for
both create and edit since they share `ModuleForm.vue`; a backend guard on
the update path is deferred to a follow-up if it proves necessary.

## 2. Root cause confirmed

- Exactly one production API-create path exists for train:
  `app/api/v1/carbon_report_module.py:934` →
  `CarbonReportModuleWorkflow.create()` (`app/workflows/carbon_report_module.py:152`)
  → `handler.validate_create()` → `DataEntryService.create()`. Grepped every
  caller of `DataEntryService(...).create(` (one hit) and
  `CarbonReportModuleWorkflow(...).create(` (one hit) — confirmed.
- The #1552 Tableau API connector (`professional_travel_api_provider.py`) is
  plane-only (`DATA_ENTRY_TYPE = DataEntryTypeEnum.plane`, hardcoded
  `data_entry_type_id=DataEntryTypeEnum.plane.value` in `_load_data`) — no
  second train-creating path there.
- CSV ingestion never touches `CarbonReportModuleWorkflow.create()` — it
  builds `DataEntry` directly in `base_csv_provider.py:1347`. A guard added
  to the workflow's `create()` cannot affect CSV ingest.
- `handler.validate_create()` is the _same_ DTO for both API and CSV calls,
  so `origin_natural_key`/`destination_natural_key` can't simply become
  required `str` on the DTO — that would 422 every legitimate CSV row before
  `enrich_csv_row` gets a chance to resolve them (this is why the field was
  made optional in the first place; still true today).
- Any plain pydantic `ValidationError` inside `handler.validate_create()` is
  caught by the workflow's generic `except Exception` and reduced to
  `HTTPException(400, ...)` — so a new check must `raise HTTPException(422, ...)`
  explicitly (the `except HTTPException: raise` passthrough) to surface as a
  clean 422, not rely on the DTO layer.

## 3. Design

- **Backend, API path**: add a train-specific guard inside
  `CarbonReportModuleWorkflow.create()`, mirroring the existing
  `planner_purchase` per-type special case already in that function (same
  file, same pattern — no new hook/interface for a single consumer).
- **Backend, CSV path**: `enrich_csv_row`'s `not_found` branch returns a row
  error instead of logging a warning and falling through.
- **Frontend**: extract the "was a suggestion actually picked" check into a
  small pure function in `src/utils/` (this repo's established pattern for
  testable `ModuleForm.vue` logic — see `fieldInteraction.ts`,
  `module-table-access.ts`, `submitCreateItem.ts`; every existing
  `frontend/tests/unit/*.spec.ts` other than one trivial `app.spec.ts` smoke
  test follows this "extract + plain-test" shape, none mount `ModuleForm.vue`
  itself), wire it into `validateField`'s `direction-input` branch so
  submission is blocked with an inline error _before_ any network call.
- `pre_compute`'s existing `if not origin_natural_key or not
destination_natural_key: return {}` guard is **left untouched** — it's the
  recalc-time resilience net for legacy rows persisted under the old rules
  (no DB backfill policy), same as plane's equivalent guard. This fix closes
  the _ingest-time_ hole, not recalc-time defense for old data.

## 4. Global constraints

- Backend functions ≤40 lines, ≤2 nesting levels ([guardrails.md](../contributing/guardrails.md)).
- No `# type: ignore` / `@ts-expect-error`.
- No SQL in routes/workflows — this change adds no queries, pure validation.
- Every change ships with a test on the side it touches; every bug fix ships
  a regression test that fails without the fix.
- i18n: any new user-facing string goes in both locales in the same `.ts`
  file entry (`en`/`fr` keys together — this repo keeps both locales in one
  file per module, not separate `en-US`/`fr-CH` files).

---

## Task 1: CSV `not_found` becomes a hard row error

**Files:**

- Modify: `backend/app/modules/professional_travel/handlers.py:319-381` (`ProfessionalTravelTrainModuleHandler.enrich_csv_row`)
- Test: `backend/tests/unit/services/data_ingestion/test_train_enrich_csv_row.py`
- Test (found during implementation, needs updating too): `backend/tests/integration/services/data_ingestion/test_travel_pg.py::test_train_unknown_station_persists_entry_without_emission` — an #1183 discovery test that pins the exact old "persist, 0 emissions" contract for this case with a real Postgres CSV run (`travel_trains_unknown_station.csv` fixture, destination `Atlantis`). Renamed to `test_train_unknown_station_is_rejected_as_row_error`; asserts `parent.result == IngestionResult.ERROR` and `n_entries == 0`. Needs `pg_dsn` (Postgres) to run — not run as part of this plan's targeted `uv run pytest` steps; verify separately with `make run-db` + `uv run pytest tests/integration/services/data_ingestion/test_travel_pg.py -k train`.

**Interfaces:**

- Consumes: `LocationService.resolve_train_station_for_csv(name, country_code) -> (Location | None, str)` — returns `(None, "not_found")` on zero matches (`app/services/location_service.py:101-129`, unchanged).
- Produces: `enrich_csv_row(data, session) -> (dict, str | None)` — `not_found` now returns a non-None `error_msg` (was `None`). `base_csv_provider._process_row` already treats any non-None `enrich_error` as a hard row error (`base_csv_provider.py:1332-1334`, unchanged).

- [x] **Step 1: Write the failing test**

Add to `backend/tests/unit/services/data_ingestion/test_train_enrich_csv_row.py`:

```python
@pytest.mark.asyncio
async def test_train_enrich_not_found_is_a_hard_row_error(monkeypatch) -> None:
    """#1186: zero station matches must reject the row, not persist it
    silently. Supersedes #1183's original choice to mirror plane's
    unknown-IATA behavior here — warn-and-persist on a WARNING nobody reads
    is a silent fallback, not real parity.
    """

    async def _fake_resolve(self, name: str, country_code: str):
        return None, "not_found"

    monkeypatch.setattr(
        "app.modules.professional_travel.handlers."
        "LocationService.resolve_train_station_for_csv",
        _fake_resolve,
    )

    handler = ProfessionalTravelTrainModuleHandler()
    data = {
        "origin_name": "Atlantis",
        "origin_country_code": "CH",
        "destination_name": "Geneva",
        "destination_natural_key": "train:ch:geneva:46.2104:6.1428",
    }

    enriched, err = await handler.enrich_csv_row(data, MagicMock())

    assert err is not None
    assert "Atlantis" in err
    assert "origin_natural_key" not in enriched
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/services/data_ingestion/test_train_enrich_csv_row.py::test_train_enrich_not_found_is_a_hard_row_error -v`
Expected: FAIL — `err` is `None` (current code logs a warning and falls through to `return enriched, None`).

- [x] **Step 3: Implement**

In `backend/app/modules/professional_travel/handlers.py`, replace the tail
of the `for role in ("origin", "destination")` loop in `enrich_csv_row`:

```python
            station, reason = await loc_service.resolve_train_station_for_csv(
                name=name,
                country_code=country_code,
            )
            if station is not None:
                enriched[f"{role}_natural_key"] = station.natural_key
                continue
            if reason.startswith("ambiguous"):
                return (
                    data,
                    f"{role} station {name!r} in {country_code}: {reason} "
                    f"— supply {role}_country_code or fix the upstream data",
                )
            return (
                data,
                f"{role} station {name!r} not found in locations table for "
                f"country {country_code!r} — check spelling or supply "
                f"{role}_natural_key directly",
            )
        return enriched, None
```

(This deletes the `logger.warning(...)` call it replaces — no import cleanup
needed, `logger` is still used elsewhere in the file.)

Update the method's docstring (the "Resolution failure modes split" section)
to match — `not_found` is now a hard row error, not a persist-with-warning:

```python
        Resolution failure modes split:
          - missing country_code: row fails — operator must supply it.
          - ambiguous (>1 match): row fails — operator must hand-curate the
            upstream data (or pick a more specific name).
          - not_found (0 matches): row fails — operator must fix the name or
            supply {role}_natural_key directly. (#1186: previously persisted
            the entry with a WARNING and no natural_key, mirroring plane's
            unknown-IATA path; that silent zero-emission gap is why this
            issue exists.)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/services/data_ingestion/test_train_enrich_csv_row.py -v`
Expected: all 4 tests PASS (3 existing + the new one).

- [x] **Step 5: Commit**

```bash
cd backend
git add app/modules/professional_travel/handlers.py tests/unit/services/data_ingestion/test_train_enrich_csv_row.py
git commit -m "fix(#1186): train CSV not_found station is a hard row error, not a silent skip"
```

---

## Task 2: API create requires a resolved natural_key

**Files:**

- Modify: `backend/app/workflows/carbon_report_module.py:152-221` (`CarbonReportModuleWorkflow.create`)
- Modify: `backend/app/modules/professional_travel/data_entries.py:110-125` (stale comment cleanup)
- Test: `backend/tests/unit/workflows/test_carbon_report_module_create.py`

**Interfaces:**

- Consumes: `create_payload: dict` (already built in `create()` from `item_data` + type/module ids), `DataEntryTypeEnum.train`.
- Produces: `HTTPException(422, detail="TRAIN_STATION_NOT_RESOLVED")` raised before any DB write when a train create is missing either natural_key. No change to the method's public signature or return type.

- [x] **Step 1: Write the failing tests**

Add to `backend/tests/unit/workflows/test_carbon_report_module_create.py`:

```python
def _train_item_data(**overrides: object) -> dict:
    base = {
        "user_institutional_id": "123456",
        "origin_name": "Geneva",
        "destination_name": "Lausanne",
        "origin_country_code": "CH",
        "destination_country_code": "CH",
        "origin_natural_key": "train:ch:geneva:46.2104:6.1428",
        "destination_natural_key": "train:ch:lausanne:46.5197:6.6323",
        "cabin_class": "second",
        "number_of_trips": 1,
    }
    return {**base, **overrides}


@pytest.mark.asyncio
async def test_create_train_without_natural_key_is_rejected():
    """#1186: origin_natural_key/destination_natural_key stay optional on
    the DTO (CSV rows validate before enrich_csv_row resolves them), so a
    train API create missing them must be rejected here — not left to
    silently zero-emission at recalc time.
    """
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    workflow = CarbonReportModuleWorkflow(session)

    with (
        patch(
            "app.workflows.carbon_report_module.DataEntryService",
            return_value=data_entry_service,
        ),
        patch(
            "app.workflows.carbon_report_module.DataEntryEmissionService",
            return_value=emission_service,
        ),
        patch(
            "app.workflows.carbon_report_module.CarbonReportModuleService",
            return_value=module_service,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await workflow.create(
                carbon_report_module=MagicMock(id=42, module_type_id=1),
                data_entry_type_id=DataEntryTypeEnum.train.value,
                item_data=_train_item_data(origin_natural_key=None),
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "TRAIN_STATION_NOT_RESOLVED"
    data_entry_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_train_with_natural_key_succeeds():
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    data_entry_service.create = AsyncMock(
        return_value=DataEntryResponse(
            id=7,
            data_entry_type_id=DataEntryTypeEnum.train.value,
            carbon_report_module_id=42,
            data=_train_item_data(),
        )
    )
    workflow = CarbonReportModuleWorkflow(session)

    with (
        patch(
            "app.workflows.carbon_report_module.DataEntryService",
            return_value=data_entry_service,
        ),
        patch(
            "app.workflows.carbon_report_module.DataEntryEmissionService",
            return_value=emission_service,
        ),
        patch(
            "app.workflows.carbon_report_module.CarbonReportModuleService",
            return_value=module_service,
        ),
    ):
        response = await workflow.create(
            carbon_report_module=MagicMock(id=42, module_type_id=1),
            data_entry_type_id=DataEntryTypeEnum.train.value,
            item_data=_train_item_data(),
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    assert response.id == 7
    data_entry_service.create.assert_awaited_once()
```

- [x] **Step 2: Run tests to verify the rejection test fails**

Run: `cd backend && uv run pytest tests/unit/workflows/test_carbon_report_module_create.py -k train -v`
Expected: `test_create_train_without_natural_key_is_rejected` FAILS (no
`HTTPException` raised today — the create silently proceeds).
`test_create_train_with_natural_key_succeeds` should already PASS (no guard
yet to block it).

- [x] **Step 3: Implement the guard**

In `backend/app/workflows/carbon_report_module.py`, inside `create()`,
right after `validated_data = handler.validate_create(create_payload)` and
before building `data_entry_create`:

```python
            validated_data = handler.validate_create(create_payload)

            # DTO-level ``str | None`` is intentional (CSV rows validate
            # before ``enrich_csv_row`` resolves the natural_key — #1186) so
            # this can't be a pydantic required-field check. API/UI creates
            # always carry the resolved natural_key from the station
            # autocomplete (ModuleForm's direction-input guard, #1186); a
            # payload missing it means that guard was bypassed or a raw API
            # client skipped station lookup.
            if data_entry_type == DataEntryTypeEnum.train and (
                not create_payload.get("origin_natural_key")
                or not create_payload.get("destination_natural_key")
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="TRAIN_STATION_NOT_RESOLVED",
                )

            data_entry_create = DataEntryCreate(
                **validated_data.model_dump(exclude_unset=True)
            )
```

In `backend/app/modules/professional_travel/data_entries.py`, replace the
stale comment on `ProfessionalTravelTrainHandlerCreate` (it asked a question
this task answers):

```python
    # Optional here (unlike plane's origin_iata) because CSV rows validate
    # before enrich_csv_row resolves the natural_key from origin_name +
    # origin_country_code (#1183). The API path has no such staging: a
    # missing natural_key there is rejected in
    # CarbonReportModuleWorkflow.create (#1186), not by this DTO.
    origin_natural_key: str | None = None
    destination_natural_key: str | None = None
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/workflows/test_carbon_report_module_create.py -v`
Expected: all tests PASS, including the two new ones.

- [x] **Step 5: Commit**

```bash
cd backend
git add app/workflows/carbon_report_module.py app/modules/professional_travel/data_entries.py tests/unit/workflows/test_carbon_report_module_create.py
git commit -m "fix(#1186): reject train API creates missing a resolved station natural_key"
```

---

## Task 3: Frontend — block submit when a station wasn't actually selected

**Files:**

- Create: `frontend/src/utils/directionLocationValidation.ts`
- Test: `frontend/tests/unit/direction-location-validation.spec.ts`
- Modify: `frontend/src/components/organisms/module/ModuleForm.vue` (`validateField`'s `direction-input` branch, ~line 985)
- Modify: `frontend/src/i18n/professional_travel.ts`

**Interfaces:**

- Produces: `isTravelLocationResolved(travelMode: 'plane' | 'train', iata: unknown, naturalKey: unknown): boolean` — pure function, no Vue/i18n dependency, importable directly by the test.

- [x] **Step 1: Write the failing test**

Create `frontend/tests/unit/direction-location-validation.spec.ts`:

```typescript
/**
 * Regression test for #1186 — a traveler can type a station/airport name
 * into the direction-input free-text field without picking an autocomplete
 * suggestion. `form.origin`/`form.destination` (the display text) then
 * looks non-empty and the old "required" check passed, but the identifier
 * the backend actually needs — `origin_iata` for plane, `origin_natural_key`
 * for train — never got set, so the entry silently persisted with zero
 * emissions.
 */
import { test, expect } from "@playwright/test";

import { isTravelLocationResolved } from "../../src/utils/directionLocationValidation";

test("#1186: plane resolves only when origin_iata is set from the autocomplete", () => {
  expect(isTravelLocationResolved("plane", "GVA", undefined)).toBe(true);
  expect(isTravelLocationResolved("plane", undefined, undefined)).toBe(false);
});

test("#1186: train resolves only when natural_key is set from the autocomplete", () => {
  expect(
    isTravelLocationResolved(
      "train",
      undefined,
      "train:ch:geneva:46.2104:6.1428",
    ),
  ).toBe(true);
  // Typed a name, never picked a suggestion — natural_key stays unset.
  expect(isTravelLocationResolved("train", undefined, undefined)).toBe(false);
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test-ct -- direction-location-validation.spec.ts`
Expected: FAIL — `src/utils/directionLocationValidation.ts` doesn't exist yet.

- [x] **Step 3: Implement the pure helper**

Create `frontend/src/utils/directionLocationValidation.ts`:

```typescript
/**
 * #1186: a traveler can type a station/airport name into the direction
 * inputs without picking an autocomplete suggestion. The free-text value
 * (`form.origin`/`form.destination`) then looks non-empty, but the
 * identifier the backend resolves distance/emissions from — `origin_iata`
 * for plane, `origin_natural_key` for train — never gets set. The entry
 * would otherwise persist with zero emissions and only a backend log line
 * to notice it.
 */
export function isTravelLocationResolved(
  travelMode: "plane" | "train",
  iata: unknown,
  naturalKey: unknown,
): boolean {
  return travelMode === "plane" ? Boolean(iata) : Boolean(naturalKey);
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test-ct -- direction-location-validation.spec.ts`
Expected: both tests PASS.

- [x] **Step 5: Wire it into `ModuleForm.vue` and add the i18n key**

In `frontend/src/i18n/professional_travel.ts`, add next to
`error-same-destination` (~line 170):

```typescript
  [`${MODULES.ProfessionalTravel}-error-location-not-selected`]: {
    en: 'Select a location from the suggestions',
    fr: 'Sélectionnez un lieu dans les suggestions',
  },
```

In `frontend/src/components/organisms/module/ModuleForm.vue`, add the
import near the other utility imports, and extend the `direction-input`
branch of `validateField` (~line 985):

```typescript
import { isTravelLocationResolved } from "src/utils/directionLocationValidation";
```

```typescript
  if (effectiveType === 'direction-input') {
    errors.origin = null;
    errors.destination = null;

    if (i.required) {
      const requiredMsg = i.requiredMessageKey
        ? $t(i.requiredMessageKey)
        : $t('validation_required');
      if (!form.origin || form.origin === '') {
        errors.origin = requiredMsg;
        return false;
      }
      if (!form.destination || form.destination === '') {
        errors.destination = requiredMsg;
        return false;
      }

      const travelMode = getTravelMode();
      if (travelMode) {
        const notSelectedMsg = $t(
          `${MODULES.ProfessionalTravel}-error-location-not-selected`,
        );
        if (
          !isTravelLocationResolved(
            travelMode,
            form.origin_iata,
            form.origin_natural_key,
          )
        ) {
          errors.origin = notSelectedMsg;
          return false;
        }
        if (
          !isTravelLocationResolved(
            travelMode,
            form.destination_iata,
            form.destination_natural_key,
          )
        ) {
          errors.destination = notSelectedMsg;
          return false;
        }
      }
    }

    // ... existing same-destination check unchanged below
```

- [x] **Step 6: Type-check and lint**

Run: `cd .. && make lint && make type-check` (from repo root — per
`AGENTS.md`, never run frontend type-check from inside `frontend/`).
Expected: both pass, no new `@ts-expect-error`.

- [x] **Step 7: Commit**

```bash
cd frontend
git add src/utils/directionLocationValidation.ts tests/unit/direction-location-validation.spec.ts src/components/organisms/module/ModuleForm.vue src/i18n/professional_travel.ts
git commit -m "fix(#1186): block travel form submit when a station wasn't actually selected"
```

---

## Task 4: Docs — keep the plan trail accurate

**Files:**

- Modify: `docs/src/implementation-plans/1183-train-csv-country-code.md`
- Modify: `docs/src/implementation-plans/1186-train-natural-key-validation.md` (this file)

- [x] **Step 1: Supersede note on the 1183 plan**

Add one line under its `## 3. Required country_code in the trip resolver`
section (1183's plan currently documents `not_found` as "mirror the plane
unknown-IATA path" — that's no longer the shipped behavior after Task 1):

```markdown
> **Superseded by #1186**: the `not_found` (0 matches) case described below
> as "persist, don't error" was changed to a hard row error — see
> [1186-train-natural-key-validation.md](1186-train-natural-key-validation.md).
```

- [x] **Step 2: Flip this plan's status once Tasks 1-3 are verified green**

Change the frontmatter `status: in-progress` → `status: delivered` and bump
`last_updated`.

- [x] **Step 3: Commit**

```bash
git add docs/src/implementation-plans/1183-train-csv-country-code.md docs/src/implementation-plans/1186-train-natural-key-validation.md
git commit -m "docs(#1186): supersede note on 1183, mark 1186 plan delivered"
```

## 5. Verification (run once, after all tasks)

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/test_train_enrich_csv_row.py tests/unit/workflows/test_carbon_report_module_create.py -v
cd frontend && npm run test-ct -- direction-location-validation.spec.ts
make lint
make type-check
```

Per standing preference, the user runs the full test suite — this plan stops
at targeted pytest/test-ct runs plus `make lint`/`make type-check`.
