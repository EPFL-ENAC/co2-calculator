---
status: proposed
issue: 1491
last_updated: 2026-07-07
title: "Factor Upsert Strategy: Identity-Key Hardening, Backoffice Viewer, Bulk Delete"
summary: "Close the remaining null-classification-key gap in factor CSV ingestion, add a backoffice factor viewer, and expose bulk delete-by-entry-type for factors and data entries."
---

# Factor Upsert Strategy: Identity-Key Hardening, Backoffice Viewer, Bulk Delete

## Problem

The reporter hit duplicate `research_facilities` factors after uploading a CSV with a null
`researchfacility_id`, then re-uploading a corrected file. `researchfacility_id` is part of
the factor identity key, so the null-vs-corrected value produced two distinct identity
digests instead of one row being updated in place.

**This repo has since shipped Plan 310B** (`backend/app/services/data_ingestion/base_factor_csv_provider.py`,
`backend/app/repositories/factor_repo.py`), which changes the picture substantially:

- Identity key is `(data_entry_type_id, year, emission_type_id, classification::text)`,
  enforced by two partial unique indexes and an `INSERT ... ON CONFLICT DO UPDATE`
  (`factor_repo.py:41-72`, `127-148`). `classification` is stored as JSONB specifically so
  `classification::text` is key-order-deterministic (`app/models/factor.py:30-34`).
- The upsert preserves `factor.id` across re-uploads (so `DataEntryEmission.primary_factor_id`
  FKs stay valid) and stamps `last_seen_job_id`. A stale-sweep
  (`_delete_stale_factors`, `base_factor_csv_provider.py:597-622`) deletes rows not stamped
  by the current job — but **only runs when the upload is a clean `SUCCESS`**
  (`base_factor_csv_provider.py:541-546`): a partially-failed upload intentionally does not
  sweep, so it can't silently destroy data on operator error.
- For `research_facilities`, `researchfacility_id`/`researchfacility_name` are **already**
  required (non-`Optional`) on the _factor_ DTO,
  `ResearchFacilitiesCommonFactorCreate` (`app/modules/research_facilities/common_schemas.py:203-208`) —
  distinct from the `Optional[str] = None` the reporter quoted, which is the _data-entry_
  response/update DTO (`common_schemas.py:32`, `84`), not the factor identity path. A null
  CSV cell for these fields now raises a Pydantic `ValidationError` inside
  `handler.validate_create(...)`, caught per-row (`base_factor_csv_provider.py:393-398`) and
  recorded as a row error — not a crash, not a silently-duplicated row.
- The "None classification kind" crash is also not reproducible on the current runtime-resolver
  path: `resolve_factor_emission_type` (`app/utils/data_entry_emission_type_map.py:414-459`)
  degrades a bad/missing classification value to `None` → `get_factor_emission_type_id` raises
  `ValueError` → caught per-row (`base_factor_csv_provider.py:375-382`).

**What's actually still broken:**

1. The null-guard only exists because `ResearchFacilitiesCommonFactorCreate` happens to
   declare its identity fields as required `str`. That's per-handler DTO discipline, not a
   framework guarantee — nothing stops another handler's `*FactorCreate` from declaring an
   identity-bearing classification field as `Optional`, letting a null back into
   `classification` and into the identity key silently. `_process_row` builds `classification`
   generically off `handler.classification_fields` (`base_factor_csv_provider.py:357-365`) but
   never checks those specific fields for `None` before they become part of the identity.
2. `factor_repo.py:309-311` documents (not fixes) a real landmine: **any factor row not
   stamped by a CSV job** (manual entry, `computed`-provider updates, API) has
   `last_seen_job_id IS NULL` and is silently deleted by the _next_ CSV upload covering that
   `(det, year)`. That's the deeper "upsert strategy" question the reporter is gesturing at.
3. No backoffice visibility into what factors exist for a year/det — the only way to catch a
   duplicate today is a crash or a wrong total.
4. `DataEntrySourceEnum`/`bulk_delete_by_source[_year]` already exist on the _data-entry_ side
   (`app/models/data_entry.py:53-66`, `app/repositories/data_entry_repo.py:168-209`,
   `app/services/data_entry_service.py:375-436`) — explicitly built "enabling selective
   deletion" — but are only ever called internally by the CSV re-ingest cleanup path
   (`base_csv_provider.py`), never exposed as an admin-triggered action. No equivalent
   bulk-delete exists for `Factor` rows at all.

## Design

### 1. Identity-key hardening (straightforward, no product decision needed)

- Add one generic guard in `BaseFactorCSVProvider._process_row`
  (`base_factor_csv_provider.py`, right after the `classification` dict is built, before
  `get_factor_emission_type_id`/`validate_create`): if any value in
  `handler.classification_fields` is `None`, record a row error naming the missing field and
  skip the row. This is a single choke point — every factor CSV provider routes through
  `_process_row` — so it replaces relying on each handler's DTO annotations happening to
  agree with its own `classification_fields` list.
- Audit existing `*FactorCreate` DTOs for handlers where a `classification_fields` entry is
  typed `Optional` (mechanical grep, not a design question) and tighten those to match
  `research_facilities`' pattern, or rely solely on the new generic guard.
- Out of scope: the `computed`/`manual` provider paths (`BaseFactorUpdateProvider`) update
  factors in place by `factor.id` and never rebuild `classification` from a row loop, so
  they're structurally not exposed to this class of bug.

### 2. Rediscuss the upsert strategy (needs product decision)

Flag, don't resolve, in this plan:

- Should a factor row created outside a CSV job (manual/API/`computed`) be eligible for
  deletion by the next CSV upload that covers its `(det, year)`? Today it silently is
  (`factor_repo.py:309-311`). This is the actual "upserting doesn't reliably work" complaint —
  it's not a bug, it's an unreviewed policy baked into `last_seen_job_id IS NULL` matching the
  stale-sweep predicate.
- Is `classification::text` (raw JSON serialization) the right long-term identity, or should
  identity-bearing fields get dedicated typed columns / a canonical hash? JSONB normalizes key
  order today, which covers the obvious footgun, but the approach still couples identity to
  JSON encoding.

Both need sign-off before touching `factor_repo.py`'s conflict targets or sweep predicate —
out of scope for this plan's Steps.

### 3. Backoffice factor viewer (ask #3, straightforward)

- New read-only endpoint, e.g. `GET /api/v1/backoffice/factors` filtered by
  `data_entry_type_id` + `year` (+ pagination), backed by the already-existing
  `FactorRepository.list_by_data_entry_type` and `count_by_data_entry_type_and_year`
  (`factor_repo.py:403-465`) — no new query logic needed.
- Serialize rows via the existing `handler.to_response(factor)` (`app/schemas/factor.py:205-213`)
  for human-readable classification/values instead of raw JSON, and surface
  `last_seen_job_id` so an operator can spot rows never touched by the latest upload (early
  warning for exactly the duplicate/staleness class of bug reported here).
- Frontend: extend the existing `frontend/src/stores/factors.ts` / `frontend/src/api/factors.ts`
  rather than inventing a new list-view pattern; mirror whatever table component the other
  backoffice list pages already use.

### 4. Bulk delete by entry type/year (ask #4, mostly wiring)

- **Data entries**: capability already exists end-to-end
  (`DataEntryService.bulk_delete_by_source`, `data_entry_service.py:375-436`, backed by
  `DataEntryRepository.bulk_delete_by_source[_year]`, `data_entry_repo.py:168-209`, keyed on
  `DataEntrySourceEnum` = `USER_MANUAL` / `CSV_MODULE_PER_YEAR` /
  `CSV_MODULE_UNIT_SPECIFIC` / `API_MODULE_PER_YEAR` / `API_MODULE_UNIT_SPECIFIC` /
  `EXTERNAL_INTEGRATION`, `data_entry.py:53-66`). Just needs a backoffice-guarded endpoint,
  e.g. `DELETE /api/v1/backoffice/data-entries?module_type_id=&data_entry_type_id=&source=&year=`,
  wired to the existing service method.
- **Factors**: no equivalent bulk endpoint. Add
  `FactorRepository.bulk_delete_by_data_entry_type_and_year(data_entry_type_id, year)` as a
  thin wrapper composing the already-existing `list_id_by_data_entry_type_and_year` +
  `bulk_delete` (both in `factor_repo.py`), exposed via
  `DELETE /api/v1/backoffice/factors?data_entry_type_id=&year=`.
- **Recalc consideration (must not skip)**: `_delete_stale_factors` chains a recalc for
  affected reports today (`base_factor_csv_provider.py:600`, dispatched from
  `ingestion_tasks.py`). A manual admin delete of factors or data entries a report already
  used needs the same fan-out — or the endpoint must clearly document that reports are left
  stale and must be regenerated. Decide which before shipping the delete button; don't ship a
  delete that silently orphans reports.
- Gate both new endpoints behind the existing backoffice custom-permission-key scheme (no
  role checks in code, per repo convention) — reuse whatever key already guards other
  destructive backoffice actions rather than inventing a new one.

## Steps

- [ ] Add generic null-classification-field guard to `BaseFactorCSVProvider._process_row`; record a clear row error naming the field
- [ ] Audit all `*FactorCreate` DTOs for identity fields typed `Optional` where they shouldn't be; tighten to match `research_facilities`' pattern
- [ ] Add regression test: CSV row with a null identity-bearing classification field produces a row error, not a written factor or a crash
- [ ] Write up the two open policy questions (cross-source stale-sweep eligibility; JSON-text identity vs. dedicated columns) as a decision doc / ticket for product sign-off — do not implement either without sign-off
- [ ] Add `GET /api/v1/backoffice/factors` (filtered by `data_entry_type_id`, `year`, paginated) using existing `FactorRepository` list/count methods
- [ ] Add frontend backoffice factor-viewer page, extending `frontend/src/stores/factors.ts` / `frontend/src/api/factors.ts`
- [ ] Add `DELETE /api/v1/backoffice/data-entries` wired to existing `DataEntryService.bulk_delete_by_source[_year]`
- [ ] Add `FactorRepository.bulk_delete_by_data_entry_type_and_year` and `DELETE /api/v1/backoffice/factors` endpoint
- [ ] Decide and implement recalc/staleness handling for both new delete endpoints (chain existing recalc fan-out, or document + surface "reports stale" state)
- [ ] Gate both delete endpoints behind the existing backoffice destructive-action permission key
- [ ] Add regression tests for both bulk-delete endpoints (happy path + recalc/staleness behavior)
