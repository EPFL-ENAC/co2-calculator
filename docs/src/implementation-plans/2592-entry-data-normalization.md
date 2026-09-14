---
issue: 2592
status: delivered
last_updated: 2026-09-08
title: "Normalize pre-existing entry data payloads (audited operator pass)"
summary:
  "Plan for #2592: put the join keys stored in data_entries.data in the same
  format as the shared field types from #2585. Audited on prod and stage:
  nothing a factor lookup uses differs, so no migration ships; an operator
  script (dry run, explicit --apply) replaces it. Decided 2026-09-08 in PR
  #2585."
---

# Normalize pre-existing entry data payloads (#2592)

## Why

PR #2585 (issue #1489) normalizes the factor side: shared field types in
`app/schemas/fields.py`, applied on every DTO. Rows written before that
(factors and entries) may still hold the old format; touching them is
validated emission data, so the guardrails require a written plan reviewed
by both maintainers.

So today, after #2585, new entries are stored normalized but old entries
keep whatever format they were created with (currency `CHF`, padded codes,
mixed-case country codes). Factor resolution compares
`factor.classification[k]` to `entry.data[k]` with exact string equality,
so an old entry with a non-normalized value can silently resolve no factor
even though the matching factor exists. The compute handlers for purchase
and external cloud carry a defensive `.lower()` to paper over the currency
case; that code can only be deleted once entry data is guaranteed clean.

**Outcome (lead, 2026-09-08): no migration.** The dry run against prod and
stage found 2,147 entries to rewrite, all purchase and equipment `name` values
with a surrounding space, none validated, no join key among them, and no
factor to change at all. So the pass is not mandatory and nothing rewrites
data at deploy time. `backend/scripts/normalize_join_keys.py` carries the
rules (pinned to the DTOs), prints the audit, and rewrites by hand with
`--apply` if the whitespace is ever worth tidying.

## Keys in scope

Exactly the keys the `*HandlerCreate` DTOs type with a shared alias (or the
cabin-class mixin), per data entry type. The script carries the map
(`RULES_BY_DATA_ENTRY_TYPE`) and `tests/unit/schemas/test_join_key_normalization_rules.py`
derives the expected map from the live DTO annotations, so adding a
normalized field to a DTO without a script entry fails the test.

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

`uv run python -m scripts.normalize_join_keys` counts, per data
entry type and key, how many `data_entries` rows differ from the DTO form
and how many of those are validated, and lists values that would still fail
the vocabulary checks after normalization (an unsupported currency, an
unknown cabin class, a malformed country code) for a manual decision. The
same script does the factor side (rows to change, identities that would
collide). Run it on each platform after a deploy that touches the shared
field types and paste the output on #2592.

## Step 2: rewrite by hand, only if wanted

`uv run python -m scripts.normalize_join_keys --apply` rewrites the rows the
dry run listed, in place, in one transaction. It refuses when two factors
would collide after normalization (merge by hand first, emissions point at
them) or when a value needs a manual decision. Nothing is merged, deleted or
added; a second run finds nothing. Pinned to the DTOs by
`tests/unit/schemas/test_join_key_normalization_rules.py`, exercised on real
Postgres by `test_normalize_join_keys_script_pg.py`.

The defensive `.lower()` in the purchase and external cloud compute handlers
is deleted in the same PR: the audit shows no entry carries a non-canonical
currency.

## Step 3: recompute

Lead decision (2026-09-08): **no recompute is triggered by this pass.**
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
- **Drift between the script and the DTO types.** Pinned by the shared unit
  test pattern from #2585.

## Out of scope

- Any change to the DTOs themselves (done in #2585).
- Normalizing keys the resolver does not join on.
- Backfilling missing keys or repairing malformed entries; anything the
  audit flags as not-cleanly-normalizable is a per-case decision, not part
  of the bulk pass.
