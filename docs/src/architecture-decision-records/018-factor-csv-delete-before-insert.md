---
status: delivered
last_updated: 2026-05-05
summary: Factor CSV uploads delete then re-insert scoped by (data_entry_type_id, year) for idempotent reuploads.
---

# ADR-018: Factor CSV Idempotency via Delete-Before-Insert

**Status**: Accepted
**Date**: 2026-05-05
**Deciders**: Backend Team
**Related**: [ADR-011: Factor Classification JSONB](./011-factor-classification-jsonb.md); plan `docs/src/implementation-plans/243-data-management-full-data-flow.md`

## Context

Factor CSV uploads previously **appended** rows. Re-uploading the
same file (a routine operator action — fix a typo, re-run a
validation) duplicated every factor. Operators had no clean
"reset" path short of manual SQL.

The 310-b factor pipeline introduces upsert-in-place keyed on
`(data_entry_type_id, year, emission_type_id, classification)` and
preserves `factor.id` across uploads — that solves the FK-orphan
problem. But we still need a clear idempotency contract for the
**delete-the-rest** semantics: factors that were in the previous
CSV but not in the new one should disappear (or be marked stale).

## Decision

CSV factor providers run **delete-before-insert** scoped to the
`(data_entry_type_id, year)` of the upload, before processing
batches:

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

The repository methods
`list_id_by_data_entry_type_and_year` and
`count_by_data_entry_type_and_year` provide the audit numbers.
`bulk_delete_by_data_entry_type` accepts an optional `year`; with
`year=None` it deletes all rows for the type (backward compatible).
The deletion count is recorded in job metadata for the audit trail.

Combined with 310-b's `last_seen_job_id` stamping and JSONB
classification (ADR-011), this gives operators predictable
re-upload semantics without leaking duplicate rows.

See `docs/src/implementation-plans/243-data-management-full-data-flow.md`.

## Consequences

**Positive**:

- Same CSV uploaded twice yields the same row count.
- Operators have a clear mental model: the upload **is** the new
  truth for that `(type, year)`.
- Audit log captures `factors_deleted` per upload.

**Negative**:

- Deletion happens before insertion, so a partial-failure window
  exists where the table is empty for that scope. Mitigated by
  running inside the ingest transaction; a rollback restores the
  previous rows.
- Factors omitted from a re-upload are gone. Operators relying on
  partial CSVs to "patch" must understand this — the public docs
  flag it explicitly.

**Future direction**: 310-b's upsert-in-place + `last_seen_job_id`
allows a softer "mark stale, keep FKs" mode for production once the
operator UX accommodates "stale factor" badges.

## References

- `docs/src/implementation-plans/243-data-management-full-data-flow.md`
- `docs/src/implementation-plans/310-b-factor-pipeline.md`
- [ADR-011: Factor Classification JSONB](./011-factor-classification-jsonb.md)
