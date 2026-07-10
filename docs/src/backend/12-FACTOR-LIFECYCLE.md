# Factor Lifecycle

How emission factors get created, updated, deleted, and recomputed — the
operator-facing contract behind every factor CSV upload (#1491).

## TL;DR for operators

- **Upload a factor CSV** → rows are upserted in place, keyed on identity.
- **Corrected re-upload that fully succeeds** → replaces exactly what it
  carries and deletes everything else in its scope (stale sweep).
- **Partial upload (some rows error)** → writes what parsed, deletes
  nothing. Fix the CSV and re-upload.
- **The factor CSV is the source of truth** for its
  `(data_entry_type, year)` scope. Anything written to factors outside the
  CSV pipeline is transient and will be overwritten or swept by the next
  covering upload.
- Every successful upload chains an emission recalculation, so reports
  reflect the new factors without further action.

## Upsert semantics

Every factor CSV upload goes through
`FactorRepository.upsert_factors`: a COPY-staged
`INSERT … ON CONFLICT DO UPDATE` keyed on the factor identity

```text
(data_entry_type_id, year, emission_type_id, classification::text)
```

backed by two partial unique indexes (`year IS NOT NULL` / `year IS NULL`).

- A row whose identity already exists **updates in place**: `values` and
  `last_seen_job_id` are overwritten, `factor.id` is preserved.
- A new identity **inserts** a new row.
- Rows that fail per-row validation (bad value, unresolvable emission
  type, missing required identity field) are recorded as row errors and
  skipped — the upload continues and finishes `WARNING`.

Upsert-in-place (rather than delete-all + reinsert) is an operability
choice:

- **Partial-upload safety** — a `WARNING` upload writes what parsed and
  never deletes; operator error cannot destroy factors.
- **Blast radius** — unchanged factors and the emission rows referencing
  them stay untouched; a re-upload affects exactly the rows it carries.

`DataEntryEmission.primary_factor_id` (the emission→factor FK) is derived
state: it is rebuilt by every recalculation, so id-preservation is a
nice-to-have, not a correctness requirement.

## Stale sweep

Only when an upload finishes **100 % SUCCESS** (zero skipped rows), a
sweep deletes factors that the upload superseded:

- Scope: the `(year, data_entry_type)` combinations the upload actually
  wrote — a partial module CSV can never wipe sibling types it did not
  carry ("you replace what you upload").
- Predicate: `last_seen_job_id` predates this job **or is NULL**.
- Emission rows referencing swept factors are removed by FK cascade and
  rebuilt by the chained recalculation.

A `WARNING` or `ERROR` upload never sweeps: deleting the factors that the
failed rows would have refreshed would silently destroy data.

**Policy: the CSV is the source of truth.** Factor rows written outside
the CSV pipeline do not carry a `last_seen_job_id` stamp and are deleted
by the next covering `SUCCESS` upload. This is deliberate: the computed
factor providers (e.g. research-facilities factor updates) modify factor
`values` in place as transient state between uploads; the next CSV upload
re-asserts the canonical values. If you need a factor to survive uploads,
it must be in the CSV.

## Chained recalculation

After a successful factor upload, the ingest chains one
`emission_recalc` job per affected `(module, data_entry_type)`:

1. Every surviving data entry in the `(data_entry_type, year)` slice has
   its emissions recomputed against the new factors (set-based replace —
   stale emission rows are deleted, fresh ones written, including
   `primary_factor_id`).
2. The last recalculation chains one `aggregation` job, which rewrites
   `carbon_report_module.stats` and `carbon_report.stats`.

So factors → emissions → stats is a one-way derivation; only factors and
data entries are operator-owned state.

## What re-importing a corrected CSV does

1. Corrected rows upsert over their previous identity (same `factor.id`).
2. New rows insert.
3. If the upload is 100 % `SUCCESS`: rows present in the previous upload
   but absent from this one are swept (e.g. the duplicate identities the
   old file created).
4. Recalculation + aggregation chain, and reports reflect the corrected
   factors.

If the corrected upload is only partially successful (`WARNING`), steps 1
and 2 still happen for the good rows, step 3 does not — re-upload a fully
clean file to trigger the sweep.

## Inspecting and deleting factors from the backoffice

- `GET /api/v1/backoffice/factors?data_entry_type_id=&year=` — paginated
  viewer for the factors of one `(data_entry_type, year)` scope. Each row
  exposes `last_seen_job_id`, so rows **not** asserted by the latest
  upload are identifiable.
- `DELETE /api/v1/backoffice/factors?data_entry_type_id=&year=` — bulk
  delete of a scope. Emission rows cascade; an `emission_recalc` job is
  dispatched automatically so stats do not go stale.
- `DELETE /api/v1/backoffice/data-entries?…` — bulk delete of data
  entries by type + source (optionally module-scoped); also chains a
  recalculation.
