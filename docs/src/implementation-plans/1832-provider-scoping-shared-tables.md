---
status: deferred
issue: 1832
last_updated: 2026-09-10
title: "Provider (tenant) isolation for factors, pipelines, connectors, locations, building_rooms"
summary: "Add a provider column (user_provider_enum) to every table that still leaks across tenants, scope all reads/writes like year_configuration does, and backfill by duplicating reference data per provider so TEST starts with a full mirror of ACCRED."
---

# Provider scoping for shared tables (#1832)

> **Deferred, 2026-09-10 — merged as a record, not as a queue item.**
>
> The decision is that **the provider is not changed mid-deploy**, which
> removes the trigger for every leak below: they require two tenants to be
> live against the same database at the same time. That is an _operational_
> mitigation, so it constrains how the system is run rather than what it
> guarantees. **The leaks themselves are unchanged** — the `factors` upsert
> conflict key still has no provider, and the connector tables still show both
> tenants the same credentials.
>
> This plan is merged so the analysis is findable rather than lost in a closed
> PR: what leaks, how severely, and what the fix would cost. Nothing in it is
> scheduled.
>
> **Revisit when any of these becomes true**, because each one restores the
> trigger the mitigation removes:
>
> - a second provider needs to be live alongside ACCRED, for any length of
>   time — a TEST tenant for training or a migration rehearsal included;
> - a connector credential is added that is not shared between tenants by
>   intent (this is the one that is a disclosure rather than a corruption —
>   see the table below);
> - a factor CSV is ever uploaded under a non-ACCRED provider against the
>   shared database, deliberately or by accident. `upsert_factors` will
>   overwrite the rows ACCRED's published emissions are computed from, and
>   nothing will report an error.
>
> #1832 stays **open**, holding the risk. Closing it would assert the leaks
> are gone; they are not, they are unreachable by convention.

## Problem

`provider` (`user_provider_enum`: ACCRED / DEFAULT / TEST) scopes `users`,
`units`, `year_configuration` (PK `(year, provider)`), `data_ingestion_jobs`,
and — transitively via `unit_id` — all report/entry/emission data. Five
tables have no provider dimension and leak across tenants:

| Table                                             | Leak                                                                                                                                                     | Severity                                      |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| `factors`                                         | TEST factor CSV upload **overwrites** the rows ACCRED emissions compute from (`upsert_factors` conflict key has no provider); all lookups provider-blind | Data corruption — can drift published numbers |
| `pipelines`                                       | No provider column; `GET /data-sync/pipelines` and `GET /data-sync/recalculation-status` mix tenants                                                     | Backoffice console confusion                  |
| `connector_connections` / `connector_datasources` | Both tenants see the same connector credentials                                                                                                          | Credential exposure across tenants            |
| `locations`                                       | Global; no tenant write path today, scoped for consistency                                                                                               | Low                                           |
| `building_rooms`                                  | Global; synced/seeded, scoped for consistency                                                                                                            | Low                                           |

`year_configuration` is the reference pattern: enum column, every route
filters `col(X.provider) == current_user.provider`.

## Decisions (validated 2026-07-16)

- **Full isolation** — all five tables above get `provider`, including
  `locations` and `building_rooms`.
- **Backfill by duplication** for reference tables (`factors`, `locations`,
  `building_rooms`): existing rows become ACCRED, an identical TEST copy is
  inserted, so TEST starts with a full mirror. `pipelines` backfill from
  their child jobs' provider (orphans with no jobs → ACCRED, historical).
  Connectors backfill as ACCRED; TEST configures its own.
- **DEFAULT provider gets no duplicates.** It only exists as a column
  default today (no live tenant). Rows for it appear when a DEFAULT user
  first writes.
- **Provider source at query time** (never a request parameter):
  - routes → `current_user.provider`
  - ingestion/recalc workflows → `job.provider` (already stamped)
  - unit-scoped recompute → `unit.provider`

## Schema changes

All new columns: `provider: UserProvider`, non-nullable,
`SAEnum(UserProvider, name="user_provider_enum", native_enum=True)` with
`create_type=False` in the migration (enum already exists in PG).

- `factors` — add `provider`; both partial unique indexes gain it:
  - `(provider, data_entry_type_id, year, emission_type_id, (classification::text)) WHERE year IS NOT NULL`
  - `(provider, data_entry_type_id, emission_type_id, (classification::text)) WHERE year IS NULL`
- `pipelines` — add `provider` (plain indexed column).
- `connector_connections` — add `provider`; datasources inherit scope via
  `connection_id` FK (no own column — mirrors the unit→children pattern).
- `locations` — add `provider`; `natural_key` (and any other unique index)
  becomes `(provider, …)`.
- `building_rooms` — add `provider`; existing unique/lookup indexes gain it.

Migrations via `make db-revision`, then prune false-positive `drop_index`
calls. Data steps (backfill, duplication, repoint) are hand-added to the
generated migration — they are not expressible in model code.

## Migration data steps

1. Add columns with server default ACCRED, then drop the default
   (existing rows → ACCRED).
2. Duplicate reference rows for TEST:
   `INSERT INTO factors (…, provider) SELECT …, 'TEST' FROM factors WHERE provider = 'ACCRED'`
   (same for `locations`, `building_rooms`).
3. Repoint TEST emissions at their TEST factor duplicates:
   `data_entry_emissions.primary_factor_id` currently points at the
   (now-ACCRED) originals. Join emission → `data_entries.unit_id` →
   `units.provider = 'TEST'`, match ACCRED factor → TEST duplicate on
   `(data_entry_type_id, emission_type_id, year, classification::text)`,
   update `primary_factor_id`. Deterministic — no recompute required for
   correctness (recompute after deploy is the verification, not the fix).
4. `pipelines.provider` from any child job
   (`data_ingestion_jobs.pipeline_id`); orphans stay ACCRED.

## Code changes

**Write paths**

- `backend/app/repositories/factor_repo.py` — staging temp table DDL, COPY
  column list, both `ON CONFLICT` upsert statements, `create`, and the
  stale-factor purge queries (`last_seen_job_id` threshold) all gain
  provider. Provider comes from the ingestion job.
- Pipeline creation (`backend/app/repositories/data_ingestion.py` /
  workflow entry) stamps `provider` from the triggering job/user.
- `backend/app/services/connector_service.py` + `connector_repo.py` —
  stamp on create.
- Seeds (`backend/app/seed/seed_generic_factors.py`, units/locations/
  building-rooms seeds) — seed per provider or accept a provider argument.

**Read paths**

- `backend/app/services/factor_service.py` (`get_by_classification`,
  `get_class_subclass_map`) and `backend/app/api/v1/factors.py` — filter
  by `current_user.provider`.
- `backend/app/services/factor_resolver.py` — `resolve()` / `_get_maps`
  take provider; recompute callers pass `job.provider` / `unit.provider`.
- `backend/app/repositories/data_ingestion.py` —
  `get_recalculation_status_by_year`, `filter_scopes_with_current_factors`,
  pipeline list/detail queries gain a provider filter.
- `backend/app/api/v1/data_sync.py` — `GET /pipelines`,
  `GET /recalculation-status`, `GET /jobs` filter by
  `current_user.provider` (job creation already stamps it).
- `backend/app/api/v1/connectors.py`, `locations.py`, `building_rooms.py`,
  `taxonomies.py` — filter reads by `current_user.provider`.

**Frontend** — no changes. Scoping is derived server-side from the
authenticated user; no new request parameters, no OpenAPI surface change.

## Delivery: three PRs, ship small

1. **PR 1 — factors** (the corruption risk): schema + duplication +
   emission repoint migration, upsert/lookup/resolver/recompute scoping,
   regression tests. Highest value, standalone.
2. **PR 2 — pipelines + data-sync reads**: `pipelines.provider`, console
   and recalculation-status filtering.
3. **PR 3 — connectors + locations + building_rooms**: remaining columns,
   read filters, seeds.

Each PR carries its own migration and tests.

## Tests (regression, per guardrails)

- **Fails today:** upsert a TEST factor with the same
  `(det, year, classification)` as an existing ACCRED factor → ACCRED
  row's `values` must be unchanged; TEST row exists separately.
- `FactorResolver.resolve` returns the provider's own factor when both
  providers have one for the same classification.
- `GET /factors/...` endpoints return only `current_user.provider` rows.
- `GET /data-sync/pipelines` and `/recalculation-status` exclude the other
  provider's pipelines/jobs.
- Connector list returns only own-provider connections.
- Migration test (or scripted check on a seeded DB): duplication counts
  match and no TEST emission points at an ACCRED factor row.

## Coordination / open points

- Touches factor resolution and recompute → **both maintainers review this
  plan before code** (guardrails: "while the lead is away").
- **Branch target:** PR 1 and 2 touch pipeline/recalc internals — confirm
  whether they merge to `fix/pipeline-debug` or `dev`.
- **#1661 (remove primary_factor_id) is in progress.** If it lands first,
  the emission-repoint migration step disappears; if this lands first,
  #1661 must scope its on-demand resolution by provider. Sequence
  explicitly with the lead.
