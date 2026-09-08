---
issue: 2592
status: delivered
last_updated: 2026-09-08
title: "Normalize pre-existing entry data payloads (audited migration pass)"
summary:
  "Plan for #2592: put the join keys stored in data_entries.data in the same
  format as the shared field types from #2585, with a read-only audit script
  and an idempotent migration. Touches validated emission data; approved by
  the lead on 2026-09-08 and shipped in PR #2585 alongside the factor pass."
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

Shipped in PR #2585 itself (the lead folded the audit PRs into one on
2026-09-08), as migration `cf237968fba7`, right after the factor migration
`09fe9e551783`.

## Keys in scope

Exactly the keys the `*HandlerCreate` DTOs type with a shared alias (or the
cabin-class mixin), per data entry type. The migration carries the map
(`RULES_BY_DATA_ENTRY_TYPE`) and `tests/unit/schemas/test_entry_data_migration.py`
derives the expected map from the live DTO annotations, so adding a
normalized field to a DTO without a migration entry fails the test.

| Rule            | Same as                     | Keys                                                                                                                                                |
| --------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lower`         | `CurrencyCode`, cabin mixin | `currency` (purchase, external clouds), `cabin_class` (plane, train)                                                                                |
| `country`       | `CountryCode`               | `origin_country_code`, `destination_country_code` (train)                                                                                           |
| `identifier`    | `IdentifierKey`             | `researchfacility_id`, `researchfacility_name`                                                                                                      |
| `blank_to_none` | `OptionalClassificationKey` | `sub_class` (equipment), `subcategory` (process emissions), `purchase_additional_code`                                                              |
| `strip`         | `ClassificationKey`         | names, codes, `equipment_class`, `provider`, `service_type`, `usage_type`, `category`, `building_name`, `room_name`, `unit`, `use_unit`, IATA codes |

Non-string values and keys not listed stay untouched (`identifier` is the
one exception: a JSON number `1.0` becomes `"1"`, as the DTO does). Keys
absent from an entry are never added. Buildings `energy_type` is a factor-only
key and is not in entry data.

## Step 1: read-only audit (no writes)

`uv run python -m scripts.audit_entry_data_normalization` counts, per data
entry type and key, how many `data_entries` rows the migration would rewrite
and how many of those are validated, and lists values that would still fail
the vocabulary checks after normalization (an unsupported currency, an
unknown cabin class, a malformed country code) for a manual decision. It
imports the rules from the migration file, so it reports exactly what the
migration does. Run it on each platform before `make db-migrate` and paste
the output on #2592.

## Step 2: migration

One Alembic migration, `cf237968fba7`, same shape as `09fe9e551783`:

- Iterate the entries whose `data` contains at least one in-scope key.
- Apply the same normalization functions. The migration file carries its
  own copies, and `tests/unit/schemas/test_entry_data_migration.py` pins
  both the value rules and the key map to the live DTOs.
- `tests/integration/test_alembic_migrations.py`
  (`test_2592_entry_data_join_keys_normalized_in_place`) runs it on real
  Postgres over seeded old-style rows: join keys come out canonical, other
  keys and unmapped entry types stay byte-equal, and a downgrade +
  re-upgrade changes nothing.
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

Lead decision (2026-09-08): **no recompute is triggered by this migration.**
Entries that silently resolved no factor start matching at the next natural
recompute (a factor re-upload or an entry edit on the report). The audit
output on #2592 tells the data manager which reports that concerns before
it happens.

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
