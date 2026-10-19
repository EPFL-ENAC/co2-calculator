---
status: delivered
issue: 2992
last_updated: 2026-10-02
summary: an inline provider change on an External Clouds row 422s — the kind-change clear nulls service_type and resolve_clouds fails hard on the missing value, rolling back the edit; fix mirrors #2501 — a missing service_type resolves to no emission leaves (incomplete row, blank kg), an unknown one still raises
---

# 2992 — provider change on a cloud row must yield an incomplete row, not a 422

Same failure class as [#2501](2501-building-change-incomplete-row.md)
(buildings, PR #2504): the #2050 fail-hard made an old silent clear loud.

## Root cause

1. Inline table edits PATCH one field: `{"provider": "GCP"}`
   (`ModuleInlineSelect.vue` `onValueChange` → `patchItem`).
2. `provider` is the clouds handler's `kind_field`, `service_type` its
   `subkind_field` (`backend/app/modules/external_cloud_and_ai/handlers.py`).
   `clear_dependent_fields_on_kind_change` nulls `service_type` because the
   request doesn't carry one.
3. The recompute resolves no factor (`(provider, None)` misses — every cloud
   factor carries a `service_type`), then `resolve_clouds`
   (`.../external_cloud_and_ai/emissions.py`) raises
   `EmissionTypeResolutionError("No emission type for cloud service_type ''")`.
   The update workflow maps that `ValueError` to 422 and rolls back
   (`backend/app/workflows/carbon_report_module.py` `update`).

Net: no inline provider change on a cloud row could succeed. Nothing was
corrupted (full rollback). Re-selecting the _current_ provider is not a kind
change, so it returned 200.

Second trigger, same fix: a row persisted with an empty `service_type`
(pre-#2050 the same clear succeeded silently and zeroed the row) 422'd on
**every** inline edit, spent amount and currency included.

The ECB exchange-rate path (the only other 422 source on this update path)
was ruled out by the maintainer on 2026-10-02.

**The issue's technical leads were off.** On update, DTO validation failures
(`validate_spent_amount`, `validate_currency`, `ClassificationKey` blanks)
are caught by the workflow's validation `try` and surface as **400**, not 422. `ExternalCloudHandlerUpdate` has no `_non_empty` validator.

## Decided approach (maintainer, 2026-10-02 — mirrors #2501)

A cloud row whose `service_type` is missing is **incomplete**: it persists,
contributes no emission rows, renders blank kg with `row-incomplete` styling.
The user re-picks a service type inline and the row completes. An _unknown_
`service_type` still fails hard. Missing means incomplete; wrong means error.

What #2501 needed that clouds already had:

| #2501 change                                   | Clouds                                                                                 |
| ---------------------------------------------- | -------------------------------------------------------------------------------------- |
| `kind_dependent_fields` to clear the room name | not needed — the subkind clear already nulls `service_type`, nothing else is dependent |
| `requiredFieldIds` for incomplete rendering    | `isCompleteExternalCloud` (`ModuleTable.vue`) already requires `service_type`          |
| inline subkind options from the right source   | taxonomy subkinds _are_ service types — already right                                  |
| frontend clears the subkind on kind change     | `resetSubclass` in `useEquipmentClassOptions` already does                             |
| incomplete gate in the resolver                | **was missing — this is the fix**                                                      |

Consistency check: the AI submodule in the same table already behaves this
way. A provider change nulls `usage_type`, no factor matches,
`resolve_computations` returns `[]`, and the row has no emission rows with no
raise (`resolve_ai` keys on `provider`, which is present).

### Rejected alternative: keep `service_type` across a provider change

Every provider in `external_clouds_factors.csv` carries every service type,
so `service_type` is not truly provider-dependent. Keeping it would make a
provider change a one-step edit. Cost:

- a new handler knob to skip the subkind clear;
- the shared `resetSubclass` composable to teach, since it blanks the cell
  client-side;
- a silent-null-kg risk the day a provider lacks a service type, because the
  UI would call the row complete.

That is a new pattern for one module. Revisit only if users find the
two-step edit annoying.

## What shipped

**Incomplete gate in `resolve_clouds`.** If `service_type` is missing or
empty, return `[]`. `DataEntryEmissionService.prepare_create` treats `[]` as
"emits nothing" and returns early; `upsert_by_data_entry` deletes the row's
stale emission rows. The unknown-value raise stays.

`resolve_clouds` also files **factor** rows (`resolve_factor_emission_type`).
A blank-`service_type` factor row still fails there via `if not types`
(generic "No emission type is mapped" message instead of the named one).
A test pins it.

No frontend change: the incomplete rendering, the option source and the
client-side clear already exist. The kg cell is blank because the backend
returns `kg_co2eq: null`.

No data migration: legacy rows with an empty `service_type` are legitimately
incomplete, and the user completes them inline.

**Not generalized.** The sibling resolvers that fail hard on a missing
subkind are not reachable by an inline kind change:

- plane/train: `category` is not inline-editable;
- animal facilities: the inline name edit doesn't PATCH `researchfacility_id`;
- process emissions and AI: they key on the kind itself.

A missing `cabin_class`, say, is invalid data, not an incomplete row. The
gate stays local, as #2501's did.

## Tests

The #2501 workflow test mocks `DataEntryEmissionService`, so it never reaches
the resolver; a clouds clone would pass without the fix, and the generic
clear is already pinned in `test_module_handler_service.py`. These fail
without the fix:

- **Unit** (`backend/tests/unit/modules/test_emission_type_fail_hard.py`):
  `resolve_clouds` returns `[]` for `service_type` absent, `None` or `""`;
  `resolve_factor_emission_type(external_clouds, {"service_type": ""})`
  still raises. The existing `UNMAPPED_ROWS` case (`"quantum"`) still pins
  the unknown-value raise.
- **Integration**
  (`backend/tests/integration/modules/external_cloud_and_ai/test_emission_type_resolution.py`):
  a cloud entry with `service_type: None` — next to a factor for its
  provider under a real service type — goes through the real
  `prepare_create` and produces no emission rows, without raising and
  without a kind-only factor fallback.

## Related, out of scope

- #2793 — Enter doesn't commit the spending cell (same table, keyboard
  handling, separate fix).
- #2792 — chart values (unrelated).
- #2801 — Planner project-name length 422 (different module and cause).
