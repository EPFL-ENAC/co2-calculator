---
status: delivered
last_updated: 2026-05-05
summary: Production factor CSV uploads use upsert-in-place keyed on (data_entry_type_id, year, emission_type_id, classification) with last_seen_job_id stamping; delete-before-insert is the local-dev seed pattern only.
---

# ADR-018: Factor CSV Idempotency — Upsert in Production, Delete-Before-Insert in Local Seeds

**Status**: Accepted
**Date**: 2026-05-05
**Deciders**: Backend Team
**Related**: [ADR-011: Factor Classification JSONB](./011-factor-classification-jsonb.md); plan `docs/src/implementation-plans/243-data-management-full-data-flow.md`; plan `docs/src/implementation-plans/310-b-factor-pipeline.md`

## Context

Factor CSV uploads previously **appended** rows. Re-uploading the
same file (a routine operator action — fix a typo, re-run a
validation) duplicated every factor. Operators had no clean
"reset" path short of manual SQL.

Two ingest contexts have different constraints:

- **Production CSV upload** (`POST /sync/factors/...`) runs against
  a populated database with FK references from existing data
  entries. Wholesale `DELETE` would either orphan FKs or cascade
  through downstream tables. It also runs as a tracked
  `DataIngestionJob` with a `job_id` for audit.
- **Local seed scripts** (`LocalFactorCSVProvider`) run against an
  empty or scratch database during `make seed-data` / dev bootstrap.
  No FK risk, no `DataIngestionJob` to stamp.

Both need idempotent re-runs, but the production path needs FK
preservation that delete-before-insert cannot offer.

## Decision

Two complementary strategies, selected by the provider class.

### Production: upsert keyed on the factor identity tuple

Production CSV ingest runs through
`BaseFactorCSVProvider._upsert_batch` →
`FactorRepo.upsert_factors(batch, current_job_id=self.job_id)`
(`backend/app/services/data_ingestion/base_factor_csv_provider.py:201,477`).
Each row is keyed on
`(data_entry_type_id, year, emission_type_id, classification)`
(the JSONB identity introduced by ADR-011). On match, the existing
`factor.id` is preserved and the row is updated in place; on miss,
a new row is inserted. Every row touched by the upload has its
`last_seen_job_id` stamped to the current job.

"Delete-the-rest" semantics is achieved by **stale-row detection**,
not physical delete: factors whose `last_seen_job_id` predates the
latest job for `(data_entry_type_id, year)` are surfaced via the
stale-factor query and can be reviewed / marked / removed by
operators with FK-aware tooling.

### Local seeds: delete-before-insert scoped to (type, year)

`LocalFactorCSVProvider`
(`backend/app/services/data_ingestion/csv_providers/local_seed.py`)
overrides `_upsert_batch` to stay on the legacy `bulk_create` path
because seed runs have no `DataIngestionJob` and therefore no
`job_id` to stamp. Before inserting, it deletes existing rows
scoped to `(data_entry_type_id, year)`:

```python
if self.data_entry_type_id and self.year:
    existing = await factor_service.count_by_data_entry_type_and_year(
        data_entry_type_id=int(self.data_entry_type_id),
        year=self.year,
    )
    await factor_service.bulk_delete_by_data_entry_type(
        data_entry_type_id=int(self.data_entry_type_id),
        year=self.year,
    )
    stats["factors_deleted"] = existing
```

This is safe in seed context because the database is fresh and no
FK pressure exists. `FactorStatsDict.factors_deleted` is explicitly
documented as "set by local-seed delete-and-insert path; 0 in
upsert path" — the field's value at runtime tells you which
strategy ran.

See `docs/src/implementation-plans/243-data-management-full-data-flow.md`
and `docs/src/implementation-plans/310-b-factor-pipeline.md`.

## Consequences

**Positive**:

- Production uploads preserve `factor.id` across re-uploads, so
  existing FK references in `data_entry_emissions` keep working.
- Same CSV re-uploaded twice yields the same logical row set in
  both contexts (idempotent).
- `last_seen_job_id` gives operators a queryable stale-factor list
  without committing to a destructive delete.
- Audit log captures `factors_deleted` (seeds) or `affected`
  (production upsert count) per upload.

**Negative**:

- Two code paths — `_upsert_batch` for production,
  `bulk_create` + scoped delete for seeds — must both be tested.
  Production paths must never silently fall through to the seed
  branch (asserted by the `job_id` requirement in the base
  `_upsert_batch`).
- Stale-row cleanup in production is operator-driven, not
  automatic. The doc surface (operator runbook) must call out the
  stale-factor query and the recommended cadence.
- Seed-only behavior: factors omitted from a re-seeded CSV are
  gone. Seed scripts must remain authoritative for the `(type,
  year)` they touch.

**Future direction**: surface the stale-factor list in the
operator UI (badges, bulk-archive action) so production cleanup
moves out of SQL and into the same UX as upload.

## References

- `docs/src/implementation-plans/243-data-management-full-data-flow.md`
- `docs/src/implementation-plans/310-b-factor-pipeline.md`
- [ADR-011: Factor Classification JSONB](./011-factor-classification-jsonb.md)
