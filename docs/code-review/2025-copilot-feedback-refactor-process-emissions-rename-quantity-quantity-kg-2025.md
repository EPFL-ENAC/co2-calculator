# Bot Review TODOs: PR #2168

Source Branch: `refactor/2025-processemissions-quantity-kg`
---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR performs an end-to-end rename of the Process Emissions quantity field from `quantity` to `quantity_kg` across backend schemas/handlers, stored `data_entries.data` JSON, CSV ingest/template fixtures, and frontend module configuration/i18n to align code with the updated data-description contract.

**Changes:**

- Rename Process Emissions DTO field + handler/formula + frontend field id/i18n key to `quantity_kg`.
- Add a guarded Alembic data-only json rewrite migration (`quantity` → `quantity_kg`) scoped to `data_entry_type_id = 50` with an exact-inverse downgrade.
- Update CSV fixtures/templates and expand backend tests to pin the new header and ensure legacy `quantity` CSVs fail visibly.

### Reviewed changes

Copilot reviewed 23 out of 23 changed files in this pull request and generated 3 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                           | Description                                                                            |
| ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| frontend/src/i18n/process_emissions.ts                                                         | Renames the Process Emissions i18n label key to `.inputs.quantity_kg`.                 |
| frontend/src/constant/module-config/process_emissions.ts                                       | Updates the Process Emissions field id/labelKey from `quantity` to `quantity_kg`.      |
| frontend/src/components/organisms/module/ModuleTable.vue                                       | Updates Process Emissions completeness check to require `quantity_kg`.                 |
| frontend/public/templates/processemissions_template.csv                                        | Updates template CSV header to `quantity_kg` while preserving BOM.                     |
| docs/src/implementation-plans/2025-processemissions-quantity-kg-rename.md                      | Adds implementation plan documenting the rename, migration, and tests.                 |
| docs/src/backend/csv-seed-formats/inventory.md                                                 | Updates documented process emissions CSV columns to `quantity_kg`.                     |
| backend/app/modules/process_emissions/data_entries.py                                          | Renames DTO field/validators to `quantity_kg`.                                         |
| backend/app/modules/process_emissions/handlers.py                                              | Updates sort map + formula to read `quantity_kg` from entry JSON/context.              |
| backend/app/core/data_entry_permissions.py                                                     | Updates editable field set for process emissions user provenance to `quantity_kg`.     |
| backend/app/seed/random_generator/seed_data_entries.py                                         | Updates seeded process emissions payload key to `quantity_kg`.                         |
| backend/alembic/versions/2026_08_18_1147-09ec5dcb3688_rename_process_emissions_quantity_to_.py | Adds data-only json migration renaming the stored JSON key (upgrade/downgrade).        |
| backend/tests/unit/modules/test_process_emissions_schemas.py                                   | Adds unit coverage for create/update DTO behavior around `quantity_kg`.                |
| backend/tests/unit/core/test_data_entry_permissions.py                                         | Updates expected editable field set for process emissions to `quantity_kg`.            |
| backend/tests/unit/services/test_simulator_plan_service.py                                     | Updates simulator plan test entries/assertions to use `quantity_kg`.                   |
| backend/tests/unit/services/test_simulator_plan_reference_year_perf.py                         | Updates perf test seed entries to use `quantity_kg`.                                   |
| backend/tests/unit/services/test_data_entry_emission_service.py                                | Updates emission service tests to use `quantity_kg`.                                   |
| backend/tests/unit/repositories/test_data_entry_repo.py                                        | Updates repo tests to use `quantity_kg` in process emissions entry JSON.               |
| backend/tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py                | Updates integration seed data for process emissions to use `quantity_kg`.              |
| backend/tests/integration/services/data_ingestion/test_quantity_kg_migration_pg.py             | Adds integration test to pin migration behavior + idempotency + reversibility.         |
| backend/tests/integration/services/data_ingestion/test_csv_ingest_matrix_pg.py                 | Adds regression asserting legacy `quantity` header fails visibly and persists nothing. |
| backend/tests/integration/services/data_ingestion/conftest.py                                  | Registers a trimmed CSV fixture key for the legacy-header test case.                   |
| backend/tests/fixtures/csv/process_emissions_smoke.csv                                         | Updates smoke fixture header to `quantity_kg`.                                         |
| backend/tests/fixtures/csv/process_emissions_legacy_quantity.csv                               | Adds legacy-header CSV fixture used by the regression test.                            |

</details>

---

💡 <a href="/EPFL-ENAC/co2-calculator/new/dev?filename=.github/skills/code-review/SKILL.md" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Add a `code-review` agent skill</a> or configure MCP servers for context-aware, tailored reviews. <a href="https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review#mcp-servers-and-agent-skills" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Learn more in the docs.</a>
---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 24 out of 24 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (2)</summary>

**backend/app/modules/process_emissions/data_entries.py:22**

- `DataEntryPayloadMixin.unflatten_payload` copies all incoming keys verbatim into `data` (app/schemas/data_entry.py:39-48). With the current DTOs, a payload that includes the legacy `quantity` key alongside `quantity_kg` can still validate and end up persisting `data["quantity"]`, which conflicts with the “no dual path” goal and can leave dead/legacy keys in stored JSON. Consider adding a `@model_validator(mode="before")` on both create/update DTOs to explicitly reject any input containing `quantity` (either top-level or inside an explicit `data` dict), so the legacy key is never accepted/persisted.

```
class ProcessEmissionsHandlerCreate(DataEntryCreate):
    category: str
    subcategory: str | None = None
    quantity_kg: float
    note: str | None = None
```

**backend/tests/integration/services/data_ingestion/test_quantity_kg_migration_pg.py:48**

- The comment above `_DET_IT_EQUIPMENT` says the control is “purchase entries”, but the constant and seed data are for IT equipment (`_DET_IT_EQUIPMENT = 61`). Please align the comment with what the test actually does (or switch the control det to a purchase type) to avoid confusion when maintaining the migration test.

```
# ``DataEntryTypeEnum.process_emissions`` / ``it_equipment`` — the second is
# the control: purchase entries keep their own unrelated ``quantity`` field.
_DET_PROCESS_EMISSIONS = 50
_DET_IT_EQUIPMENT = 61
```

</details>

---

### File: `backend/app/modules/process_emissions/data_entries.py` (Line 43) — Copilot

`ProcessEmissionsHandlerUpdate` makes `quantity_kg` optional, but `DataEntryPayloadMixin.unflatten_payload` copies _all_ non-meta keys into `data`. Because `DataEntryRepository.update()` merges `data` dicts, an update payload containing legacy `quantity` can be accepted and persisted (reintroducing the deprecated key) instead of failing loudly. Add explicit validation on create/update to reject payloads that include `quantity` (e.g., a model-level validator that raises when `'quantity' in data`).
---

### File: `backend/tests/unit/modules/test_process_emissions_schemas.py` (Line 61) — Copilot

`test_create_rejects_legacy_quantity_field` only asserts the error mentions `quantity_kg`; it doesn’t prove that the legacy `quantity` key is explicitly rejected (and there is no test that an _update_ payload with `quantity` fails). Add a regression test that `ProcessEmissionsHandlerUpdate.model_validate({...,"quantity": ...})` raises, so the old key can’t be silently persisted via PATCH.
---

### File: `backend/tests/integration/services/data_ingestion/test_quantity_kg_migration_pg.py` (Line 48) — Copilot

Comment mismatch: the control DET used here is `it_equipment` (61), but the comment says “purchase entries keep their own unrelated `quantity` field”. Update the comment to match the actual control type (or change the control DET) so the test’s intent is unambiguous.
---

---

## Action Items

### Maintainability / refactoring

- [ ] **`backend/app/schemas/data_entry.py:37-48`** — `DataEntryPayloadMixin.unflatten_payload` copies _every_ non-meta payload key into `data`, so a create payload carrying `quantity_kg` **and** a stray `quantity` persists both; the dead key then rides into report exports. Verified: `ProcessEmissionsHandlerCreate.model_validate({…, 'quantity_kg': 12.5, 'quantity': 99}).data` → `{'category':…, 'quantity_kg': 12.5, 'quantity': 99}`, and `create()` (`app/workflows/carbon_report_module.py:112-116`) applies no field allowlist. **Fix: skip in this PR.** The hole is generic to every module and every unknown key — not a gap in this rename — and the bot's suggested per-DTO "reject `quantity`" validator is a one-off guard that would have to be re-added for each future rename. The real fix is constraining `data` to declared fields (e.g. `extra="forbid"` on the payload mixin), which is a validation-scheme decision — record it as an input to #1489 rather than bolting a special case onto one module.

  _What the bot got wrong:_ it located the defect on the **update** path ("`DataEntryRepository.update()` merges `data` dicts, an update payload containing legacy `quantity` can be accepted and persisted"). That does not hold. `process_emissions` is not policy-exempt (`is_policy_exempt` covers only planner kinds + `building_embodied_energy`), so the #951 layer at `app/workflows/carbon_report_module.py:286-315` runs: `editable_fields(process_emissions, …, USER)` is now `{category, subcategory, quantity_kg}` and `ALWAYS_WRITABLE_FIELDS` is `{note}`, so a PATCH carrying `quantity` lands in `changed_locked_fields` → **403 `FIELD_NOT_EDITABLE`**. The PATCH vector the comment describes is already closed — by the very line this PR changed (`app/core/data_entry_permissions.py:121`). Its follow-up suggestion, a DTO-level test asserting `ProcessEmissionsHandlerUpdate.model_validate({…, 'quantity': …})` raises, would fail: the DTO accepts it by design and the rejection happens a layer up. The positive case that actually matters — `quantity_kg` being editable at all, which the plan's first draft missed — is already pinned by the parametrized case in `tests/unit/core/test_data_entry_permissions.py:128-134`.

- [ ] **`backend/tests/integration/services/data_ingestion/test_quantity_kg_migration_pg.py:46-49`** — Optional legibility fix. The bot's claim is **wrong**: DET 61 (`it_equipment`) is declared under `# purchase` in `DataEntryTypeEnum` (`app/models/data_entry.py:38-42`), registered on `PurchaseModuleHandler.registration_keys`, and `PurchaseHandlerCreate` does carry its own `quantity` — so the comment is accurate as written. But the constant name reads as an equipment-module type and demonstrably misled a reviewer. Fix: rename `_DET_IT_EQUIPMENT` → `_DET_PURCHASE_IT_EQUIPMENT`. No behaviour change.
