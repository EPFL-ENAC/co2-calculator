---
status: delivered
issue: 1153
last_updated: 2026-08-14
title: "Travel traveller resolution: -1 / null sentinels — Implementation Plan"
summary: "Task-by-task plan replacing __other_internal__/__other_external__ with '-1' and JSON null across the ingestion provider, create/response DTOs, the repo-level resolution comment, an Alembic data migration, and the already-shipped frontend selector/resolver/table/chart consumers."
---

# Travel traveller resolution: `-1` / `null` sentinels — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `__other_internal__` / `__other_external__` string
sentinels for `user_institutional_id` with `"-1"` (Internal other) and JSON
`null` (External other), so every Professional Travel row resolves to a
Headcount name, "Internal other", or "External other" without ever
overwriting a source SCIPER that fails to resolve.

**Architecture:** No new column, no FK, no synthetic `User` rows —
`user_institutional_id` stays a free-text string inside `DataEntry.data`
(JSONB). Two constants (`TRAVELER_OTHER_INTERNAL = "-1"`,
`TRAVELER_OTHER_EXTERNAL = None`/`null`) are defined once per language and
reused everywhere. The existing correlated-subquery resolution in
`data_entry_repo.py` needs no logic change — it already scopes correctly by
`carbon_report_module_id` and SQL's `NULL = NULL → NULL` already makes the
External sentinel safe. The work is: (1) point the ingestion provider and
the create/response DTOs at the new sentinels, (2) migrate the two legacy
string values in existing data, (3) fix two latent bugs in the
already-shipped frontend resolver where a loose `== null` check would
swallow the new `null`-as-External-other value into a blank dash.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy (async), Pydantic v2, Alembic,
pytest (`uv run pytest`); Vue 3 + Quasar 2, TypeScript, Playwright
(`tests/unit/*.spec.ts` run via `playwright-ct.config.ts`, no vitest).

**Spec:** [1153-traveler-sentinel-resolution-prd.md](1153-traveler-sentinel-resolution-prd.md)

## Global Constraints

- **No `traveller_type` column, no synthetic `User` rows.** (PRD §2, §11)
- **Never overwrite a source SCIPER that fails to resolve against
  Headcount** — an unmatched SCIPER (e.g. `"45005"`) stays `"45005"`
  forever; only the two known legacy literals (`__other_internal__`,
  `__other_external__`) are migrated. (PRD §1, §6)
- **`"-1"` is the one reserved sentinel string.** No other negative-looking
  value carries special meaning. (PRD §7)
- **External other is JSON `null` with the key present**, never an absent
  key. (PRD §2, decided in brainstorming 2026-08-14)
- **Headcount matching stays scoped to `carbon_report_module_id`** (unit +
  report year), stricter than the PRD's plain `unit_id` — do not loosen
  this. (PRD §3)
- **Traveler stays Create-only** — do not add an update path for
  `user_institutional_id` as part of this plan. (PRD §5, §11)
- Backend tests: `cd backend && uv run pytest <path> -q`. Frontend unit
  specs: `cd frontend && rtk playwright test -c playwright-ct.config.ts
<path>`. Frontend type-check (unproxied, per house rule — `rtk tsc` green
  does not guarantee `vue-tsc` passes): `cd frontend && make type-check`.

---

### Task 1: Backend — ingestion provider sentinel constants

**Files:**

- Modify: `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py:21-25`
- Test: `backend/tests/unit/services/data_ingestion/test_professional_travel_api_provider.py`

**Interfaces:**

- Produces: `TRAVELER_OTHER_INTERNAL: str = "-1"`, `TRAVELER_OTHER_EXTERNAL: None = None`, both importable from `app.services.data_ingestion.api_providers.professional_travel_api_provider`. `transform_data`'s existing blank-SCIPER branch (`sciper_raw if sciper_raw and str(sciper_raw).strip() else TRAVELER_OTHER_EXTERNAL`, line ~112-116) needs no edit — only the constant's value changes.

- [ ] **Step 1: Add a failing assertion pinning the new sentinel type**

In `backend/tests/unit/services/data_ingestion/test_professional_travel_api_provider.py`, find `test_allows_missing_sciper` (in `TestTransformData`) and add a stronger literal assertion after the existing one:

```python
    async def test_allows_missing_sciper(self, provider):
        # #1153: SCIPER is no longer mandatory — a traveler with no EPFL
        # SCIPER still comes through, tagged with the external-traveler
        # sentinel the frontend resolves to "Other traveler (external)".
        records = [self._make_record(SCIPER="")]
        result = await provider.transform_data(records)
        assert len(result) == 1
        assert result[0]["user_institutional_id"] == TRAVELER_OTHER_EXTERNAL
        # Pin the sentinel scheme itself (not just the imported symbol):
        # External other is real JSON null, not a string sentinel.
        assert result[0]["user_institutional_id"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/services/data_ingestion/test_professional_travel_api_provider.py::TestTransformData::test_allows_missing_sciper -v`
Expected: FAIL — `result[0]["user_institutional_id"]` is currently the string `"__other_external__"`, not `None`.

- [ ] **Step 3: Update the sentinel constants**

In `professional_travel_api_provider.py`, replace lines 21-25:

```python
# Sentinel ``user_institutional_id`` for a traveler with no EPFL SCIPER
# (#1153). Must match ``TRAVELER_OTHER_EXTERNAL`` in
# frontend/src/constant/module-config/traveler-options.ts, which resolves it
# to the "Other traveler (external)" display label.
TRAVELER_OTHER_EXTERNAL = "__other_external__"
```

with:

```python
# Sentinel ``user_institutional_id`` values for a traveler not tied to a
# resolvable Headcount identity (#1153, revised to the -1/null scheme —
# see docs/src/implementation-plans/1153-traveler-sentinel-resolution-prd.md).
# Must match the same-named constants in
# frontend/src/constant/module-config/traveler-options.ts.
# - INTERNAL: traveler has a SCIPER but it doesn't resolve against this
#   report's Headcount roster. Not assigned by ingestion (a Tableau row
#   either has a SCIPER or doesn't) — read-time resolution only, defined
#   here for centralized reuse (tests, future create-DTO validation).
# - EXTERNAL: traveler has no SCIPER at all. Ingestion assigns this on a
#   blank/None/whitespace SCIPER.
TRAVELER_OTHER_INTERNAL = "-1"
TRAVELER_OTHER_EXTERNAL = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/services/data_ingestion/test_professional_travel_api_provider.py -v`
Expected: PASS, all tests in the file (this constant swap doesn't change any other assertion since the other tests import the symbol rather than hardcoding the string).

- [ ] **Step 5: Pin the literal contract**

Add near the top of `TestTransformData` (or as a standalone test) in the same test file:

```python
def test_sentinel_constants_are_the_agreed_literals():
    """Pins the exact wire values — frontend traveler-options.ts must match."""
    assert TRAVELER_OTHER_INTERNAL == "-1"
    assert TRAVELER_OTHER_EXTERNAL is None
```

Add `TRAVELER_OTHER_INTERNAL` to the existing import line at the top of the test file (it already imports `TRAVELER_OTHER_EXTERNAL`).

- [ ] **Step 6: Run the full file and commit**

Run: `cd backend && uv run pytest tests/unit/services/data_ingestion/test_professional_travel_api_provider.py -v && uv run ruff check app/services/data_ingestion/api_providers/professional_travel_api_provider.py tests/unit/services/data_ingestion/test_professional_travel_api_provider.py`
Expected: PASS, ruff clean.

```bash
git add backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py backend/tests/unit/services/data_ingestion/test_professional_travel_api_provider.py
git commit -m "feat(travel-api): switch traveler sentinels to -1/null (#1153)"
```

---

### Task 2: Backend — nullable `user_institutional_id` on Create and Response DTOs

**Files:**

- Modify: `backend/app/modules/professional_travel/data_entries.py`
- Test: Create `backend/tests/unit/modules/test_professional_travel_schemas.py`

**Interfaces:**

- Consumes: nothing from Task 1.
- Produces: `ProfessionalTravelPlaneHandlerCreate.user_institutional_id: str | None`, `ProfessionalTravelTrainHandlerCreate.user_institutional_id: str | None`, `ProfessionalTravelPlaneHandlerResponse.user_institutional_id: str | None`, `ProfessionalTravelTrainHandlerResponse.user_institutional_id: str | None`. Task 3's repo test constructs rows relying on the Response DTO accepting `None`/`"-1"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/modules/test_professional_travel_schemas.py`:

```python
"""Traveler sentinel validation for Professional Travel DTOs (#1153).

user_institutional_id is a free-text SCIPER string inside DataEntry.data —
no FK, no enum. "-1" (Internal other) and null (External other) must
validate on both the Create DTOs (frontend form submission, PR #1153/#2117)
and the Response DTOs (existing rows read back from the DB must not fail
serialization now that External-other rows persist a real null).
"""

import pytest
from pydantic import ValidationError

from app.modules.professional_travel.data_entries import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelPlaneHandlerResponse,
    ProfessionalTravelTrainHandlerCreate,
    ProfessionalTravelTrainHandlerResponse,
)

_PLANE_META = {
    "data_entry_type_id": 1,
    "carbon_report_module_id": 1,
    "data": {},
    "origin_iata": "GVA",
    "destination_iata": "ZRH",
    "cabin_class": "economy",
}
_TRAIN_META = {
    "data_entry_type_id": 2,
    "carbon_report_module_id": 1,
    "data": {},
    "origin_name": "Lausanne",
    "destination_name": "Geneva",
    "origin_country_code": "CH",
    "destination_country_code": "CH",
    "cabin_class": "second",
}


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_plane_create_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelPlaneHandlerCreate.model_validate(
        {**_PLANE_META, "user_institutional_id": sciper}
    )
    assert item.user_institutional_id == sciper


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_train_create_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelTrainHandlerCreate.model_validate(
        {**_TRAIN_META, "user_institutional_id": sciper}
    )
    assert item.user_institutional_id == sciper


def test_plane_create_still_requires_the_field() -> None:
    payload = {k: v for k, v in _PLANE_META.items()}
    with pytest.raises(ValidationError):
        ProfessionalTravelPlaneHandlerCreate.model_validate(payload)


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_plane_response_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelPlaneHandlerResponse.model_validate(
        {
            "id": 1,
            "data_entry_type_id": 1,
            "carbon_report_module_id": 1,
            "source": None,
            "user_institutional_id": sciper,
            "origin_iata": "GVA",
            "destination_iata": "ZRH",
        }
    )
    assert item.user_institutional_id == sciper


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_train_response_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelTrainHandlerResponse.model_validate(
        {
            "id": 1,
            "data_entry_type_id": 2,
            "carbon_report_module_id": 1,
            "source": None,
            "user_institutional_id": sciper,
            "origin_name": "Lausanne",
            "destination_name": "Geneva",
        }
    )
    assert item.user_institutional_id == sciper
```

- [ ] **Step 2: Run tests to verify the sentinel/None cases fail**

Run: `cd backend && uv run pytest tests/unit/modules/test_professional_travel_schemas.py -v`
Expected: the `None` parametrization of each `*_accepts_sentinel_and_real_sciper` test FAILS with a pydantic `ValidationError` (`user_institutional_id` is currently `str`, non-optional); the `"123456"`/`"-1"` cases and `test_plane_create_still_requires_the_field` already PASS (they don't need the type change).

- [ ] **Step 3: Widen the four fields**

In `backend/app/modules/professional_travel/data_entries.py`, change all four occurrences of `user_institutional_id: str` to `user_institutional_id: str | None` — in `ProfessionalTravelPlaneHandlerResponse`, `ProfessionalTravelTrainHandlerResponse`, `ProfessionalTravelPlaneHandlerCreate`, `ProfessionalTravelTrainHandlerCreate`. No other field changes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/modules/test_professional_travel_schemas.py -v`
Expected: PASS, all cases.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/professional_travel/data_entries.py backend/tests/unit/modules/test_professional_travel_schemas.py
git commit -m "feat(travel): accept null/-1 user_institutional_id on travel DTOs (#1153)"
```

---

### Task 3: Backend — end-to-end resolution matrix through the repo + safety comment

**Files:**

- Modify: `backend/app/repositories/data_entry_repo.py:870-880` (comment only, no logic change)
- Test: `backend/tests/unit/repositories/test_data_entry_repo.py`

**Interfaces:**

- Consumes: `TRAVELER_OTHER_INTERNAL` from Task 1
  (`app.services.data_ingestion.api_providers.professional_travel_api_provider`),
  the widened Response DTOs from Task 2.
- Produces: nothing new — this task only proves the existing
  `DataEntryRepository.get_submodule_data(carbon_report_module_id: int,
data_entry_type_id: int, limit: int, offset: int, sort_by: str,
sort_order: str, filter: str | None = None, institutional_id_filter: str
| None = None, exclude_planner_snapshots: bool = False) ->
SubmoduleResponse` round-trips the full matrix without raising and
  without ever rewriting a stored value.

- [ ] **Step 1: Write the failing (well: currently-erroring) test**

Append to `backend/tests/unit/repositories/test_data_entry_repo.py`:

```python
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.api_providers.professional_travel_api_provider import (
    TRAVELER_OTHER_INTERNAL,
)


# ======================================================================
# Traveler sentinel resolution matrix (#1153, -1/null scheme)
# ======================================================================


def _plane_entry(module_id: int, sciper: str | None) -> DataEntry:
    return DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={
            "user_institutional_id": sciper,
            "origin_iata": "GVA",
            "destination_iata": "ZRH",
            "cabin_class": "economy",
        },
    )


def _member_entry(module_id: int, sciper: str | None, name: str) -> DataEntry:
    return DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.member,
        status=DataEntryStatusEnum.PENDING,
        data={"user_institutional_id": sciper, "name": name, "sius_code": "51", "fte": 1.0},
    )


@pytest.mark.asyncio
async def test_traveler_resolution_matrix(db_session: AsyncSession):
    """PRD §4 matrix, driven through the real get_submodule_data query.

    Every row must round-trip its stored user_institutional_id unchanged
    (never overwritten by the resolver), regardless of whether a Headcount
    match exists.
    """
    repo = DataEntryRepository(db_session)

    module_a = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    module_b = CarbonReportModule(
        carbon_report_id=2,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module_a)
    db_session.add(module_b)
    await db_session.flush()

    # Headcount: "123456" is a member of module_a's report only.
    db_session.add(_member_entry(module_a.id, "123456", "Ada Lovelace"))
    # A different unit/year's Headcount also has "999999" — must NOT resolve
    # to module_a's travel row with the same SCIPER (unit isolation, PRD §4).
    db_session.add(_member_entry(module_b.id, "999999", "Wrong Unit Person"))
    await db_session.flush()

    rows = {
        "matched": _plane_entry(module_a.id, "123456"),
        "external": _plane_entry(module_a.id, None),
        "internal_explicit": _plane_entry(module_a.id, TRAVELER_OTHER_INTERNAL),
        "unresolved_source_id": _plane_entry(module_a.id, "45005"),
        "wrong_unit_match": _plane_entry(module_a.id, "999999"),
    }
    for entry in rows.values():
        db_session.add(entry)
    await db_session.flush()

    response = await repo.get_submodule_data(
        carbon_report_module_id=module_a.id,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    by_id = {item.id: item for item in response.items}

    # Every stored value survives unchanged — resolution never rewrites data.
    assert by_id[rows["matched"].id].user_institutional_id == "123456"
    assert by_id[rows["external"].id].user_institutional_id is None
    assert (
        by_id[rows["internal_explicit"].id].user_institutional_id
        == TRAVELER_OTHER_INTERNAL
    )
    assert by_id[rows["unresolved_source_id"].id].user_institutional_id == "45005"
    assert by_id[rows["wrong_unit_match"].id].user_institutional_id == "999999"
```

Add `DataEntryStatusEnum` to the existing `app.models.data_entry` import line
at the top of the file if not already imported (it already imports
`DataEntry`, `DataEntryTypeEnum`; check before adding to avoid a duplicate
import).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/repositories/test_data_entry_repo.py::test_traveler_resolution_matrix -v`
Expected: FAILS at construction/validation — `by_id[rows["internal_explicit"].id].user_institutional_id` raises `KeyError` or the DTO raises `ValidationError` for the `None` row, because Task 2 hasn't landed yet in isolation. If Tasks 1-2 are already merged by the time this runs, this test should already PASS (it's a characterization test proving the existing subquery logic — described in the PRD as needing zero changes — actually holds); in that case skip Step 2's "must fail" expectation and proceed straight to Step 3 (add the comment) since there is no red state left to observe.

- [ ] **Step 3: Add the safety comment (no logic change)**

In `backend/app/repositories/data_entry_repo.py`, immediately before the existing comment block at line ~871 (`# A person can hold multiple headcount roles...`), add:

```python
                # Both TRAVELER_OTHER_INTERNAL ("-1") and External-other
                # (real SQL NULL) rely on this equality never spuriously
                # matching a MemberEntry: no real SCIPER is ever "-1", and
                # SQL's NULL = NULL evaluates to NULL (not true) — so an
                # External-other travel row can never match a Headcount
                # member who also has no SCIPER yet (#951 made that
                # optional too). See
                # docs/src/implementation-plans/1153-traveler-sentinel-resolution-prd.md §5.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/repositories/test_data_entry_repo.py -v`
Expected: PASS, full file.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/data_entry_repo.py backend/tests/unit/repositories/test_data_entry_repo.py
git commit -m "test(travel): pin traveler-sentinel resolution matrix through get_submodule_data (#1153)"
```

---

### Task 4: Backend — Alembic data migration for legacy sentinel values

**Files:**

- Create: `backend/alembic/versions/<generated>.py`

**Interfaces:**

- Consumes: nothing (pure data migration, independent of Tasks 1-3's Python code).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Generate the revision skeleton**

Run: `cd backend && make db-revision message="migrate legacy traveler sentinels to -1 and null"`

This runs `uv run alembic revision --autogenerate -m "..."` and fills in
`down_revision` from the current head automatically — do not hand-pick a
revision id. Since this is a data-only change with no model/column diff,
autogenerate should produce empty `upgrade()`/`downgrade()` bodies (same as
`2026_07_22_1444-2c7f5cf1c9de_migrate_mice_research_facility_type_to_.py`,
which is the template for Step 2). If autogenerate emits unrelated noise
(e.g. a stray index), prune it — see `feedback_alembic_via_make_db_revision`
convention.

- [ ] **Step 2: Write the migration body**

Fill in the generated file's `upgrade()` and `downgrade()`:

```python
def upgrade() -> None:
    """Rewrite legacy string traveler sentinels to -1 / null (#1153)."""
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', '"-1"')::json
            WHERE data->>'user_institutional_id' = '__other_internal__'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', 'null')::json
            WHERE data->>'user_institutional_id' = '__other_external__'
            """
        )
    )


def downgrade() -> None:
    """Restore the legacy string sentinels — the exact inverse."""
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', '"__other_internal__"')::json
            WHERE data->>'user_institutional_id' = '-1'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', '"__other_external__"')::json
            WHERE data->>'user_institutional_id' IS NULL
              AND data::jsonb ? 'user_institutional_id'
            """
        )
    )
```

Note the downgrade's External-other `WHERE` clause: `data->>'user_institutional_id' IS NULL AND data::jsonb ? 'user_institutional_id'` — matches only rows where the key is _present_ with a null value (this migration's own contract), not rows where the key is absent entirely (e.g. non-travel data entries, which have no such key at all and must not be touched). The `::jsonb` cast is required: `data_entries.data` is Postgres `json`, and the `?` (has-key) operator is `jsonb`-only — found and fixed during Task 4's implementation (2026-08-14), documented here for consistency.

Update the module docstring at the top of the generated file to explain the
"why" (mirror the mice migration's docstring style): this migration exists
because #1153's traveler sentinels moved from ad-hoc strings to
`"-1"`/`null`, and this repo's DB persists across deploys (backfills ship
with the code, not "moot after reseed").

- [ ] **Step 3: Verify upgrade/downgrade apply cleanly**

Run: `cd backend && uv run alembic upgrade head` against your local dev DB
(start one via `docker compose up -d db` if not already running), then `uv
run alembic downgrade -1` to confirm the inverse also applies without error.
Expected: both complete with no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): migrate legacy __other_internal__/__other_external__ sentinels (#1153)"
```

---

### Task 5: Frontend — `traveler-options.ts`: new sentinel values, fixed resolver, extracted cell/legend helpers

**Files:**

- Modify: `frontend/src/constant/module-config/traveler-options.ts`
- Test: `frontend/tests/unit/travel-other-traveler.spec.ts`

**Interfaces:**

- Produces:
  - `TRAVELER_OTHER_INTERNAL: string = '-1'`
  - `TRAVELER_OTHER_EXTERNAL: null = null`
  - `resolveTravelerName(userInstitutionalId: string | null | undefined, memberName: string | undefined, t: (key: string) => string): string` — behavior changed: `undefined` → `'-'`; `null` → External label (previously both collapsed to `'-'`).
  - New: `resolveTravelerCellText(userInstitutionalId: string | null | undefined, headcountMembersMap: Map<string, string>, currentUserInstitutionalId: string | null | undefined, currentUserDisplayName: string, t: (key: string) => string): string` — consumed by Task 6 (`ModuleTable.vue`).
  - New: `travelerSentinelMapEntries(t: (key: string) => string): [string, string][]` — consumed by Task 7 (`ModuleCharts.vue`). Returns `[TRAVELER_OTHER_INTERNAL, label]` and `['', label]` — the trips-map endpoint coerces a `null` SCIPER to `''` server-side (`data_entry_repo.py:1363`, `tid = traveler_id or ""`), so the External entry is keyed `''`, not `TRAVELER_OTHER_EXTERNAL`.

- [ ] **Step 1: Write the failing tests**

Replace the first test in `frontend/tests/unit/travel-other-traveler.spec.ts`
(`'#1153: absent traveler id renders a dash'`) — it currently asserts `null`
renders `'-'`, which is the exact bug this task fixes:

```ts
test("#1153: no data yet (undefined) renders a dash", () => {
  expect(resolveTravelerName(undefined, undefined, t)).toBe("-");
});

test("#1153: explicit null (External other) resolves to the external label, not a dash", () => {
  expect(resolveTravelerName(null, undefined, t)).toBe(
    TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  );
});
```

Append new tests for the two extracted helpers at the end of the file:

```ts
import {
  resolveTravelerCellText,
  travelerSentinelMapEntries,
} from "../../src/constant/module-config/traveler-options";

test("#1153: cell text — undefined id (loading) renders a dash", () => {
  expect(
    resolveTravelerCellText(undefined, new Map(), undefined, "Me", t),
  ).toBe("-");
});

test("#1153: cell text — external sentinel renders the external label", () => {
  expect(resolveTravelerCellText(null, new Map(), undefined, "Me", t)).toBe(
    TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  );
});

test("#1153: cell text — internal sentinel renders the internal label", () => {
  expect(
    resolveTravelerCellText(
      TRAVELER_OTHER_INTERNAL,
      new Map(),
      undefined,
      "Me",
      t,
    ),
  ).toBe(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
});

test("#1153: cell text — matching roster entry wins over the raw SCIPER", () => {
  const roster = new Map([["0184", "Ada Lovelace"]]);
  expect(resolveTravelerCellText("0184", roster, undefined, "Me", t)).toBe(
    "Ada Lovelace",
  );
});

test("#1153: cell text — current user shortcut wins when not in the roster map yet", () => {
  expect(
    resolveTravelerCellText("0184", new Map(), "0184", "Ada Lovelace", t),
  ).toBe("Ada Lovelace");
});

test("#1153: cell text — unresolved SCIPER falls back to the internal label", () => {
  expect(resolveTravelerCellText("999999", new Map(), undefined, "Me", t)).toBe(
    TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  );
});

test('#1153: trips-map legend keys external under "" (matches the backend leg coercion)', () => {
  const entries = travelerSentinelMapEntries(t);
  expect(entries).toContainEqual([
    TRAVELER_OTHER_INTERNAL,
    TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  ]);
  expect(entries).toContainEqual(["", TRAVELER_OTHER_EXTERNAL_LABEL_KEY]);
});
```

Update the file's top-of-file import list to add
`resolveTravelerCellText, travelerSentinelMapEntries` (kept as a second
import statement is fine, or merge into the existing one — match the
existing single-import-block style).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && rtk playwright test -c playwright-ct.config.ts tests/unit/travel-other-traveler.spec.ts`
Expected: FAIL — the renamed/new `null` test fails (`resolveTravelerName`
still has the loose `== null` guard), and every `resolveTravelerCellText` /
`travelerSentinelMapEntries` test fails (not exported yet).

- [ ] **Step 3: Fix the resolver and add the two helpers**

In `frontend/src/constant/module-config/traveler-options.ts`, change the
constants (lines 15-16):

```ts
export const TRAVELER_OTHER_INTERNAL = "__other_internal__";
export const TRAVELER_OTHER_EXTERNAL = "__other_external__";
```

to:

```ts
export const TRAVELER_OTHER_INTERNAL = "-1";
export const TRAVELER_OTHER_EXTERNAL = null;
```

Fix `resolveTravelerName` (the `if (userInstitutionalId == null) return '-';`
line):

```ts
export function resolveTravelerName(
  userInstitutionalId: string | null | undefined,
  memberName: string | undefined,
  t: (key: string) => string,
): string {
  // Only "no data yet" renders a dash. Once External other is a real
  // `null`, a loose `== null` here would swallow it too — use `===`.
  if (userInstitutionalId === undefined) return "-";
  if (userInstitutionalId === TRAVELER_OTHER_EXTERNAL) {
    return t(TRAVELER_OTHER_EXTERNAL_LABEL_KEY);
  }
  if (userInstitutionalId === TRAVELER_OTHER_INTERNAL) {
    return t(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
  }
  if (memberName) return memberName;
  return t(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
}
```

Append the two new exported helpers at the end of the file:

```ts
/**
 * Resolve the traveler_name table-cell text for a Professional Travel row
 * (extracted from ModuleTable.vue's renderCell so it's unit-testable
 * without mounting the component). Precedence: no data yet → dash; roster
 * match → member name; the viewer's own id → their display name (covers
 * standard users whose roster map may not include themselves); otherwise
 * delegate to resolveTravelerName for the sentinel/unresolved-SCIPER cases.
 */
export function resolveTravelerCellText(
  userInstitutionalId: string | null | undefined,
  headcountMembersMap: Map<string, string>,
  currentUserInstitutionalId: string | null | undefined,
  currentUserDisplayName: string,
  t: (key: string) => string,
): string {
  if (userInstitutionalId === undefined) return "-";
  if (userInstitutionalId !== null) {
    const member = headcountMembersMap.get(userInstitutionalId);
    if (member) return member;
    if (userInstitutionalId === currentUserInstitutionalId) {
      return currentUserDisplayName;
    }
  }
  return resolveTravelerName(userInstitutionalId, undefined, t);
}

/**
 * Legend entries for the trips-map "Other traveler" sentinels
 * (ModuleCharts.vue). get_professional_travel_trips_map coerces a null
 * SCIPER to "" server-side (`tid = traveler_id or ""`, data_entry_repo.py)
 * — that endpoint never sees TRAVELER_OTHER_EXTERNAL's real null, so the
 * legend must be keyed to what it actually emits.
 */
export function travelerSentinelMapEntries(
  t: (key: string) => string,
): [string, string][] {
  return [
    [TRAVELER_OTHER_INTERNAL, t(TRAVELER_OTHER_INTERNAL_LABEL_KEY)],
    ["", t(TRAVELER_OTHER_EXTERNAL_LABEL_KEY)],
  ];
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && rtk playwright test -c playwright-ct.config.ts tests/unit/travel-other-traveler.spec.ts`
Expected: PASS, full file.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/constant/module-config/traveler-options.ts frontend/tests/unit/travel-other-traveler.spec.ts
git commit -m "fix(travel): -1/null traveler sentinels, fix null-swallowed-to-dash bug (#1153)"
```

---

### Task 6: Frontend — wire `ModuleTable.vue` to `resolveTravelerCellText`

**Files:**

- Modify: `frontend/src/components/organisms/module/ModuleTable.vue:508` (import), `:1346-1358` (`renderCell`'s `traveler_name` branch)

**Interfaces:**

- Consumes: `resolveTravelerCellText` from Task 5.

- [ ] **Step 1: Replace the import**

Change line 508:

```ts
import { resolveTravelerName } from "src/constant/module-config/traveler-options";
```

to:

```ts
import { resolveTravelerCellText } from "src/constant/module-config/traveler-options";
```

(`resolveTravelerName` was only used at the one call site being replaced below — confirmed via repo-wide grep before this plan was written.)

- [ ] **Step 2: Replace the `traveler_name` branch**

Replace:

```ts
if (col.field === "traveler_name") {
  const user_institutional_id = row["user_institutional_id"] as
    string | undefined;
  if (user_institutional_id == null) return "-";
  const member = headcountMembersMap.value.get(user_institutional_id);
  if (member) return member;
  if (user_institutional_id === authStore.user?.institutional_id) {
    return authStore.displayName;
  }
  return resolveTravelerName(user_institutional_id, undefined, $t);
}
```

with:

```ts
if (col.field === "traveler_name") {
  const user_institutional_id = row["user_institutional_id"] as
    string | null | undefined;
  return resolveTravelerCellText(
    user_institutional_id,
    headcountMembersMap.value,
    authStore.user?.institutional_id,
    authStore.displayName,
    $t,
  );
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && make type-check`
Expected: no new errors (this is a straight behavior-preserving extraction
plus the `null` widening already covered by Task 5's helper signature).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/organisms/module/ModuleTable.vue
git commit -m "refactor(travel): wire ModuleTable traveler cell through resolveTravelerCellText (#1153)"
```

---

### Task 7: Frontend — wire `ModuleCharts.vue` to `travelerSentinelMapEntries`

**Files:**

- Modify: `frontend/src/components/organisms/module/ModuleCharts.vue:198-204` (imports), `:373-380` (`travelerSentinelLabels`)

**Interfaces:**

- Consumes: `travelerSentinelMapEntries` from Task 5.

- [ ] **Step 1: Replace the sentinel import**

Change:

```ts
import {
  TRAVELER_OTHER_INTERNAL,
  TRAVELER_OTHER_EXTERNAL,
  TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
} from "src/constant/module-config/traveler-options";
```

to:

```ts
import { travelerSentinelMapEntries } from "src/constant/module-config/traveler-options";
```

(none of the four removed symbols are used elsewhere in this file — confirmed via grep before this plan was written.)

- [ ] **Step 2: Replace `travelerSentinelLabels`**

Delete the local function:

```ts
// The two "Other traveler" sentinels (issue #1153) are stored verbatim as the
// traveler SCIPER, so seed their translated labels into every roster map — the
// map renderer would otherwise show the raw `__other_internal__` string.
function travelerSentinelLabels(): [string, string][] {
  return [
    [TRAVELER_OTHER_INTERNAL, t(TRAVELER_OTHER_INTERNAL_LABEL_KEY)],
    [TRAVELER_OTHER_EXTERNAL, t(TRAVELER_OTHER_EXTERNAL_LABEL_KEY)],
  ];
}
```

and replace its two call sites in `loadTravelerNames` (`...travelerSentinelLabels()` appears twice — the success branch's `travelerNames.value = new Map([...travelerSentinelLabels(), ...])` and the catch branch's `travelerNames.value = new Map(travelerSentinelLabels());`) with `travelerSentinelMapEntries(t)`:

```ts
async function loadTravelerNames(unitId: number, year: number | string) {
  try {
    const members = await getHeadcountMembers(
      await moduleStore.resolveCarbonReportId(unitId, year),
    );
    travelerNames.value = new Map([
      ...travelerSentinelMapEntries(t),
      ...members.map((m): [string, string] => [m.institutional_id, m.name]),
    ]);
  } catch (err) {
    // Still resolve the sentinels even if the roster fetch fails.
    travelerNames.value = new Map(travelerSentinelMapEntries(t));
    // Non-fatal: legs simply fall back to showing the raw SCIPER.
    console.error("Failed to load headcount members for trips map", err);
  }
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && make type-check`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/organisms/module/ModuleCharts.vue
git commit -m "refactor(travel): wire ModuleCharts trips-map legend through travelerSentinelMapEntries (#1153)"
```

---

### Task 8: Frontend — widen `HeadcountMemberSelect.vue`'s option type

**Files:**

- Modify: `frontend/src/components/organisms/module/HeadcountMemberSelect.vue:70-73`

**Interfaces:**

- Consumes: `TRAVELER_OTHER_EXTERNAL` (now `null`) from Task 5.

**Why this task exists:** `options` (line 99-109) already pushes `{ value:
TRAVELER_OTHER_EXTERNAL }` — once that constant is `null` (Task 5), this
violates the current `SelectOption { value: string }` interface. No
behavior change is needed beyond the type — the `q-select` binds
`modelValue: string | null` already, and `emit-value`/`map-options` pass
the raw `value` straight through untouched.

- [ ] **Step 1: Widen the interface**

Change:

```ts
interface SelectOption {
  label: string;
  value: string;
}
```

to:

```ts
interface SelectOption {
  label: string;
  value: string | null;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && make type-check`
Expected: PASS — this is a pure type widening with no new logic, so a
Playwright spec would only re-assert what Task 5's `resolveTravelerName`/
`resolveTravelerCellText` tests already cover (this component just passes
the sentinel value through unchanged); type-check is the right-sized proof
here.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/organisms/module/HeadcountMemberSelect.vue
git commit -m "fix(travel): widen HeadcountMemberSelect option type for null sentinel (#1153)"
```

---

### Task 9: Full verification pass and PR update

**Files:** none (verification only).

- [ ] **Step 1: Backend full targeted suite**

Run:

```bash
cd backend && uv run pytest \
  tests/unit/services/data_ingestion/test_professional_travel_api_provider.py \
  tests/unit/modules/test_professional_travel_schemas.py \
  tests/unit/repositories/test_data_entry_repo.py \
  tests/integration/modules/professional_travel/test_traveler_dropdown_integration.py \
  tests/unit/v1/test_travel_table_visibility.py \
  -v
```

Expected: PASS. Then run `cd backend && make lint` (ruff + mypy, per the backend `Makefile`'s `lint` target) and fix anything the sentinel type change surfaces.

- [ ] **Step 2: Frontend full targeted suite + type-check**

Run:

```bash
cd frontend && rtk playwright test -c playwright-ct.config.ts tests/unit/travel-other-traveler.spec.ts
cd frontend && make type-check
cd frontend && npx eslint src/constant/module-config/traveler-options.ts src/components/organisms/module/ModuleTable.vue src/components/organisms/module/ModuleCharts.vue src/components/organisms/module/HeadcountMemberSelect.vue
```

Expected: PASS, no lint errors.

- [ ] **Step 3: Update PR #2117**

This branch (`fix/1153-handle-travel-api-external`) already has PR #2117
open against `dev` (per the brainstorming decision to stack this work on
the same branch rather than merge #2117 first). Push the new commits:

```bash
cd /Users/guilbert/works/git/github/worktrees/co2-calculator/fix/1153-handle-travel-api-external
git push
```

Then update the PR body (`gh pr edit 2117 --body ...`) to describe the full
scope now landed — the missing-value stats and SCIPER-optional ingest from
the original PR, plus the `-1`/`null` sentinel scheme, DTO widening,
migration, and frontend fixes from this plan. Link both plan docs:
`docs/src/implementation-plans/1153-traveler-sentinel-resolution-prd.md`
and `docs/src/implementation-plans/1153-traveler-sentinel-resolution-plan.md`.

- [ ] **Step 4: Flip the plan doc status**

Update this file's frontmatter `status: in-progress` → `status: delivered`
once Steps 1-3 are green and pushed.
