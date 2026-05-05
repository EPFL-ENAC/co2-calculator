---
status: delivered
last_updated: 2026-05-05
summary: Migrate factors.classification from JSON to JSONB so cast-to-text is deterministic and the unique index actually deduplicates.
---

# ADR-011: Store `factors.classification` as JSONB

**Status**: Accepted
**Date**: 2026-05-05
**Deciders**: Backend Team
**Related**: [ADR-004: Database Selection](./004-database-selection.md); plan `docs/implementation-plans/310-b-factor-pipeline.md`

## Context

`factors.classification` was declared `Column(JSON)` to hold a small
free-form dict (e.g. `{"fuel": "diesel", "vehicle": "lorry"}`). Plan
310-b introduces a unique factor identity:

```
(data_entry_type_id, year, emission_type_id, classification)
```

enforced by a partial unique index on `(classification::text)`.
PostgreSQL `JSON` preserves the original text, so `::text` reflects
whatever order Python's `json.dumps` produced. A second caller that
writes `{"vehicle": "lorry", "fuel": "diesel"}` would be a different
`::text` value, defeating the index and silently inserting a
duplicate row.

## Decision

Migrate the column to **PostgreSQL JSONB** and the SQLAlchemy model
to `Column(JSONB)` from `sqlalchemy.dialects.postgresql`.

```sql
ALTER TABLE factors
  ALTER COLUMN classification TYPE JSONB USING classification::JSONB;
```

JSONB normalizes keys alphabetically at write time, so
`classification::text` is deterministic regardless of insertion
order. The partial unique indexes introduced by 310-b
(`uq_factor_identity` and `uq_factor_identity_no_year`) now actually
enforce identity.

Read paths return the same Python `dict`, so application code is
unchanged.

## Consequences

**Positive**:

- The unique index is a real constraint, not a coincidence. Silent
  duplicate-factor rows are eliminated.
- `ON CONFLICT DO UPDATE` upserts (310-b Part 2) preserve
  `factor.id`, keeping `DataEntry.primary_factor_id` FKs alive
  across CSV re-uploads (Strategy A entries).
- JSONB permits GIN indexes if classification queries grow.

**Negative**:

- One-time PostgreSQL-only migration; SQLite dev databases keep
  `JSON` (no behavioral difference for tests, the index is
  Postgres-scoped).
- Whitespace and key-order changes to the source CSV no longer
  produce different rows — operators must rely on values, not
  serialization, to express intent (the desirable outcome).

**Migration path**:

- Rolled out in the 310-b PR alongside the unique indexes and the
  `factor_repo.upsert_factors` code path.
- No backfill needed — JSONB normalizes existing rows on cast.

## References

- `docs/implementation-plans/310-b-factor-pipeline.md`
- `docs/implementation-plans/310-overview.md`
- [PostgreSQL JSON Types](https://www.postgresql.org/docs/current/datatype-json.html)
