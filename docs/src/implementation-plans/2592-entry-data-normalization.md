---
issue: 2592
status: in-progress
last_updated: 2026-09-01
title: "Normalize pre-existing entry data payloads (audited migration pass)"
summary:
  "Plan for #2592: put the join keys stored in data_entries.data in the same
  format as the shared field types from #2585, with a read-only audit first,
  an idempotent migration, and a scoped recompute. Touches validated emission
  data, so this plan must be approved by both maintainers before any code
  ships."
---

# Normalize pre-existing entry data payloads (#2592)

## Why

PR #2585 (issue #1489) normalizes the factor side: shared field types in
`app/schemas/fields.py`, applied on every DTO, plus a migration that puts
`factors.classification` in the same format and merges the duplicates. It
does not touch `data_entries.data` on purpose: that is validated emission
data, and the guardrails require a written plan reviewed by both
maintainers before migrating it.

So today, after #2585, new entries are stored normalized but old entries
keep whatever format they were created with (currency `CHF`, padded codes,
mixed-case country codes). Factor resolution compares
`factor.classification[k]` to `entry.data[k]` with exact string equality,
so an old entry with a non-normalized value can silently resolve no factor
even though the matching factor exists. The compute handlers for purchase
and external cloud carry a defensive `.lower()` to paper over the currency
case; that code can only be deleted once entry data is guaranteed clean.

**Depends on #2585 being merged first.** The migration mirrors the types
that PR introduces.

## Keys in scope

Exactly the join keys the shared types normalize, nothing else:

| Key                                                       | Modules                  | Rule (same as `app/schemas/fields.py`)                                         |
| --------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------ |
| `currency`                                                | purchase, external cloud | strip + lowercase                                                              |
| `country_code`                                            | train                    | strip + uppercase, `RoW` kept as is                                            |
| `cabin_class`                                             | plane, train             | strip + lowercase                                                              |
| `energy_type`                                             | buildings                | strip + lowercase                                                              |
| `purchase_institutional_code`, `purchase_additional_code` | purchase                 | strip; identifier collapse (`1.0` → `1`); blank optional → absent stays absent |
| `researchfacility_id`, `researchfacility_name`            | research facilities      | strip; identifier collapse                                                     |

Non-string values and keys not listed stay untouched. Keys absent from an
entry are never added.

## Step 1: read-only audit (no writes)

A script (run with `uv run`, not shipped as an endpoint) that counts, per
module and per key, how many `data_entries` rows would change, and how
many of those rows belong to validated entries. Output posted on #2592
before anything else happens. This tells us the blast radius and gives
the data manager a chance to veto surprises.

## Step 2: migration

One Alembic migration (via `make db-revision`), same shape as
`09fe9e551783` from #2585:

- Iterate the entries whose `data` contains at least one in-scope key.
- Apply the same normalization functions. The migration file carries its
  own copies, and a unit test pins them to the DTO types in
  `app/schemas/fields.py` so the two sides cannot drift (same pattern as
  `test_migration_normalization_matches_dto_normalization` in
  `tests/unit/schemas/test_normalized_fields.py`).
- Update only rows whose normalized `data` differs. Re-running the
  migration is a no-op (idempotent, per the pipeline guardrail).
- Unlike the factor migration there is nothing to merge or delete: entry
  rows are never deduplicated, only their `data` values change.
- Downgrade is a documented no-op (the old formats are noise, not
  information).

In the same PR: delete the defensive `.lower()` in the purchase and
external cloud compute handlers (they are marked with a comment pointing
to #2592).

## Step 3: recompute

After deploy, run a recompute scoped to the reports that own at least one
changed entry (list produced by the migration and stored in the job log).
Expected effect: entries that silently resolved no factor start matching.
Report totals can go **up** where emissions were silently missing. That is
a correction, not a regression, but the data manager must be told before
the numbers move on published reports.

## Rollout

1. Audit script output reviewed on #2592.
2. Migration + tests merged to `dev`, run on the dev platform.
3. Compare per-report totals before/after on dev, share the diff on the
   issue.
4. Only then promote `dev` → `stage` → `main`, small release, revertable.

## Risks

- **Totals change on validated reports.** Mitigated by the audit-first
  step, the dev-platform diff, and the explicit sign-off of both
  maintainers on this plan.
- **A value the normalization makes wrong** (a currency stored as a code
  the vocabulary check would reject, for example `XTS`). The audit script
  reports these instead of migrating them blindly; they get a manual
  decision each.
- **Drift between migration and DTO types.** Pinned by the shared unit
  test pattern from #2585.

## Out of scope

- Any change to the DTOs themselves (done in #2585).
- Normalizing keys the resolver does not join on.
- Backfilling missing keys or repairing malformed entries; anything the
  audit flags as not-cleanly-normalizable is a per-case decision, not part
  of the bulk pass.
