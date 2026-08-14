---
status: draft
last_updated: 2026-08-14
title: "Travel traveller resolution: replace string sentinels with -1 / null — PRD"
summary: "Replace the __other_internal__ / __other_external__ user_institutional_id hack (issue #1153) with a deterministic, backward-compatible representation: '-1' for explicit Internal other, JSON null for explicit External other, any other value is a source SCIPER resolved against Headcount scoped to (carbon_report_module_id, sciper)."
---

# Travel traveller resolution: replace string sentinels with `-1` / `null` — PRD

**Goal:** Give every Professional Travel row exactly one of three display
outcomes — a named Headcount person, "Internal other", or "External other" —
via a single centrally-resolved `user_institutional_id` contract, without
ever overwriting a source/third-party SCIPER just because it doesn't
currently resolve against Headcount.

This supersedes the string-sentinel scheme (`__other_internal__` /
`__other_external__`) shipped in issue #1153
(commit `27619683`) and extended in PR #2117.

## 1. Objective

Replace the `__other_internal__` / `__other_external__` `user_institutional_id`
hack with a deterministic representation that:

1. Displays a named person from Headcount when resolvable.
2. Displays "Internal other" for a SCIPER-bearing traveler who isn't in
   *this unit's* Headcount roster (wrong unit, not yet synced, or a
   third-party id Headcount has never heard of).
3. Displays "External other" for a traveler with no SCIPER at all.

Works for: API-imported travel (Tableau), existing travel rows, new travel
rows from the frontend form, and cases where Headcount hasn't been
retrieved/synced yet.

**Critical design principle — unchanged from the original PRD:**
**Never overwrite a source/third-party `user_institutional_id` merely because
it cannot currently be resolved against Headcount.** A travel row imported
with SCIPER `45005` stays `45005` forever, even if unit 42's Headcount has
no record of `45005` — it displays as "Internal other", but the stored value
is untouched.

## 2. Data model — adapted to this codebase

The original PRD assumed a typed, nullable, FK'd integer `user_id` column.
**We have neither a dedicated column nor a FK**: `user_institutional_id`
lives inside `DataEntry.data`, a JSONB blob, as a free-text SCIPER string.
Real EPFL SCIPERs are 6-digit numeric strings, so `"-1"` can never collide
with one.

Adapted sentinel scheme (decided in brainstorming, 2026-08-14):

| Stored `data.user_institutional_id` | Meaning |
|---|---|
| JSON key present, value `null` | Explicit External other |
| `"-1"` (string) | Explicit Internal other |
| Any other string | Source/institutional SCIPER — resolve against Headcount, scoped to `(carbon_report_module_id, sciper)` |

- **No new column.** No `traveller_type` field. No synthetic `User` rows.
- **`null` is JSON-null with the key present**, not an absent key — matches
  how every other nullable field on these DTOs already serializes, and
  survives round-tripping through Pydantic (`str | None = None`) cleanly.
- **No FK exists on `data_entries.data`** (it's JSONB), so §12 of the
  original PRD (FK rejection risk) doesn't apply — nothing to inspect or
  weaken.

Central constant, defined once per language and reused everywhere (no
scattered literal comparisons):

```python
# backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py
TRAVELER_OTHER_INTERNAL = "-1"
TRAVELER_OTHER_EXTERNAL = None
```
```ts
// frontend/src/constant/module-config/traveler-options.ts
export const TRAVELER_OTHER_INTERNAL = '-1';
export const TRAVELER_OTHER_EXTERNAL = null;
```

## 3. Traveller resolution — unchanged business logic

```python
if user_institutional_id is None:
    return EXTERNAL_OTHER
elif user_institutional_id == TRAVELER_OTHER_INTERNAL:  # "-1"
    return INTERNAL_OTHER
elif headcount contains (carbon_report_module_id, user_institutional_id):
    return HEADCOUNT_PERSON  # display that member's name
else:
    return INTERNAL_OTHER
```

**Unit scoping note:** the original PRD keys Headcount matching on
`unit_id`. This codebase already scopes strictly tighter — on
`carbon_report_module_id`, which pins both unit *and* report year. That's
already correct (a travel row must match the same report's Headcount
snapshot, not just "some year for this unit") and requires no change.

## 4. Resolution matrix (canonical — tests must cover every row)

| `user_institutional_id` | Matching Headcount `(carbon_report_module_id, sciper)` | Result |
|---:|:---:|---|
| `null` | N/A | **External other** |
| `"-1"` | N/A | **Internal other** |
| `"45005"` | Yes | **Headcount name** |
| `"45005"` | No | **Internal other** |
| `"12345"` | Yes | **Headcount name** |
| `"12345"` | No | **Internal other** |
| `"12345"` | Exists only for a different `carbon_report_module_id` | **Internal other** |

If an implementation detail conflicts with this table, the table wins.

## 5. Existing code this plugs into

Read closely during brainstorming (2026-08-14) — do not re-derive, build on
these:

- **`backend/app/repositories/data_entry_repo.py:870-897`** — the
  correlated scalar subquery joining `MemberEntry.data["user_institutional_id"]`
  against `DataEntry.data["user_institutional_id"]`, scoped to
  `carbon_report_module_id`. **No logic change needed.** SQL's three-valued
  logic (`NULL = NULL` → not true) means an External-other travel row can
  never spuriously match a Headcount member who also has no SCIPER yet
  (issue #951 made Headcount SCIPER optional too) — this safety is implicit
  in using real SQL `NULL`, not accidental; comment it in place.
- **`data_entry_repo.py:1174-1175`** — only sets `enriched_data["traveler_name"]`
  on a match; no match → key absent, response falls through to the raw
  `user_institutional_id`. This is exactly the "no backend special case"
  mechanism both sentinels rely on.
- **`data_entry_repo.py:1298,1358-1378` (`get_professional_travel_trips_map`)**
  — no Headcount join; `traveler_id` on map legs defaults to the raw SCIPER,
  and **`tid = traveler_id or ""` coerces `None` to `""`** on this endpoint
  only. This matters for §7 below (frontend map legend).
- **`carbon_report_module.py:537-619` (`list_headcount_members`)** — dropdown
  source only, not row-display resolution; unaffected.
- **`professional_travel_api_provider.py`** (PR #2117) — blank/None/whitespace
  SCIPER on ingest currently maps to a string `__other_external__`; must be
  repointed to real `None` under this scheme. A missing SCIPER from the feed
  is always External (no id at all), never Internal.
- **`app/modules/professional_travel/data_entries.py`** —
  `ProfessionalTravelPlaneHandlerCreate.user_institutional_id` /
  `TrainHandlerCreate.user_institutional_id` are currently `str`
  (non-optional); must become `str | None` to accept explicit External.
  Traveler stays **Create-only** (`app/core/data_entry_permissions.py:91`) —
  this PRD does not reopen editing it post-creation.
- **Frontend, already shipped (#1153, commit `27619683`)** —
  `frontend/src/constant/module-config/traveler-options.ts`
  (`resolveTravelerName` + the two constants),
  `HeadcountMemberSelect.vue` (the dropdown), `ModuleTable.vue` (table cell
  resolution), `ModuleCharts.vue` (trips-map legend),
  `professional-travel.ts` / `planner-module-config/index.ts` (both only
  re-export the constants, no hardcoded sentinel strings — confirmed by
  repo-wide grep). Swapping the two constants' *values* alone propagates
  everywhere **except** two real bugs the swap would introduce:

  1. **`resolveTravelerName` (`traveler-options.ts:42`)** does
     `if (userInstitutionalId == null) return '-';` before the External
     check. A loose `== null` matches both `undefined` and `null` — once
     External *is* `null`, this swallows it and always renders `'-'`
     instead of the label. Fix: `undefined` (no data loaded yet) → `'-'`;
     `null` (explicit External) → resolved label. Use `===`, not `==`.
  2. **`ModuleTable.vue:1352`** has the identical `== null` pre-check ahead
     of calling `resolveTravelerName`. Same fix.
  3. **`ModuleCharts.vue:375-379` (`travelerSentinelLabels()`)** seeds a
     `Map<string,string>` keyed by the raw sentinel value for the trips-map
     legend — but that map is looked up by `traveler_id`, which (per the
     `tid = traveler_id or ""` coercion above) arrives as `""` for
     External-other legs, never `null`. Key that legend entry under `""`
     explicitly, with a comment explaining the asymmetry with the
     JSON-row path. Internal (`"-1"`) needs no change — it survives the
     `or ""` coercion untouched (it's a truthy string).

## 6. Migration

Data-only Alembic migration, mirroring
`2026_07_22_1444-2c7f5cf1c9de_migrate_mice_research_facility_type_to_.py`'s
`jsonb_set` pattern:

```sql
-- upgrade
UPDATE data_entries SET data = jsonb_set(data::jsonb, '{user_institutional_id}', '"-1"')::json
WHERE data->>'user_institutional_id' = '__other_internal__';

UPDATE data_entries SET data = jsonb_set(data::jsonb, '{user_institutional_id}', 'null')::json
WHERE data->>'user_institutional_id' = '__other_external__';
```

`jsonb_set(..., 'null')` writes an actual JSON null with the key **present**
(matches §2's decision), not an absent key. Downgrade is the exact inverse
(swap the two `WHERE` values). Real/unresolved SCIPERs (e.g. `45005`) are
never touched — the `WHERE` only ever matches the two known legacy literals.

No FK/schema change — nothing to weaken (§12 of the original PRD doesn't
apply to a JSONB field).

## 7. Validation & constraints

- `TRAVELER_OTHER_INTERNAL = "-1"` is the one reserved sentinel; document it
  at the constant definition in both languages.
- No other negative-looking values (`"-2"`, `"-3"`, …) carry any special
  meaning — they'd just be treated as an unresolved source SCIPER (→
  Internal other via the `else` branch), which is correct and requires no
  extra guard.
- Existing valid source SCIPERs (`"45005"`, `"12345"`, …) continue to work
  unchanged.

## 8. Headcount-unavailable behavior

Two of the three outcomes never need Headcount at all:

```text
user_institutional_id = null  → External other   (no lookup)
user_institutional_id = "-1"  → Internal other    (no lookup)
user_institutional_id = "45005" → needs Headcount; "Internal other" until resolved
```

The frontend must not block or blank out a row's traveler cell merely
because the Headcount roster hasn't loaded yet — this is already how
`resolveTravelerName` is structured (`memberName` is an optional
already-looked-up value, not a required dependency), and remains true after
the §5 fixes.

## 9. Tests (resolution matrix + regressions)

**Backend**
- Extend `test_professional_travel_api_provider.py`: blank/None/whitespace
  SCIPER → `None` (not a string sentinel) — update the assertions already
  changed in PR #2117 to check `is None` instead of an `__other_external__`
  string.
- New `data_entry_repo` test driving the full §4 matrix against the real
  correlated subquery (sqlite, matching this repo's existing test DB):
  `null` → no match; `"-1"` → no match; matching SCIPER+module → name;
  matching SCIPER, different `carbon_report_module_id` → no match; unknown
  SCIPER → no match.
- DTO test: `ProfessionalTravelPlaneHandlerCreate`/`TrainHandlerCreate`
  accept `user_institutional_id: null`.

**Frontend**
- `resolveTravelerName` unit tests: `undefined` → `'-'`; `null` → External
  label; `"-1"` → Internal label; unresolved SCIPER (no `memberName`) →
  Internal label; resolved SCIPER (`memberName` set) → that name.
- `HeadcountMemberSelect.vue`: submits `"-1"` for Internal, `null` for
  External, the real `institutional_id` for a picked member; existing
  `"-1"`/`null` values on load pre-select the right option.
- `ModuleCharts.vue` trips-map legend: External-other leg (`traveler_id ""`)
  resolves to the External label via the `""`-keyed entry.

**Migration**
- `__other_internal__` → `"-1"`; `__other_external__` → JSON `null`
  (key present); untouched values (`"45005"`, real SCIPERs) unchanged;
  downgrade is the exact inverse.

## 10. Acceptance criteria

1. A user can select a Headcount person, Internal other, or External other
   from the Travel form.
2. Internal other persists as `user_institutional_id = "-1"`.
3. External other persists as `user_institutional_id = null` (key present).
4. Third-party SCIPERs (e.g. `45005`) are preserved unchanged whether or
   not they resolve.
5. An unresolved SCIPER displays as Internal other; a SCIPER matching
   Headcount for the *same* `carbon_report_module_id` displays that
   person's name; a SCIPER matching Headcount only for a different
   module/unit/year does not resolve to that person.
6. Legacy `__other_internal__` / `__other_external__` values are migrated;
   no other values are touched.
7. No `traveller_type` field, no synthetic `User` rows.
8. Resolution works with Headcount unavailable (`null`/`"-1"` need no
   lookup at all).
9. Full resolution matrix (§4) is covered by automated tests, backend and
   frontend.

## 11. Out of scope

- Making the traveler field editable after creation (stays Create-only,
  per existing `data_entry_permissions.py:91` — not reopened here).
- Any change to `get_professional_travel_trips_map`'s per-leg name
  resolution beyond the `""`-keyed legend fix (§5.3) — it already doesn't
  join Headcount and this PRD doesn't add that.
