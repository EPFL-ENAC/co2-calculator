---
status: delivered
issue: 2007
last_updated: 2026-08-24
title: "User input for the Research Facilities module (modularity for other institutions)"
summary: "Give research_facilities and animal_facilities a manual-entry form driven by the year's factor catalog, switch it off by default via the existing per-submodule inputs_deactivated flag, unlock that flag in the backoffice, and make it fail closed server-side."
---

# User input for Research Facilities (#2007)

## Problem

From #2007: _"If I want to activate the manual input for research facilities I
cannot do it. For EPFL we will not want that, but other institutions may want
to activate it. Same for animal facilities."_

#951 shipped the **rights** — the matrix already grants
`researchfacility_id` / `researchfacility_name` / `use` / `use_unit` plus delete
on user-added Research Facilities rows
(`backend/app/core/data_entry_permissions.py`) — and the generic
POST/PATCH/DELETE endpoints already work, as the Project Grant grid
(`PlannerResearchFacilityRows.vue`) demonstrates. What was missing was the
Calculator-side form, blocked by four independent gates:

1. Every field in `module-config/research-facilities.ts` carried
   `hideIn: { form: true }`, so `hasModuleForm` (`SubModuleSection.vue`) was
   false and `ModuleForm` never mounted.
2. `hasTableAction: false` on both submodules — no delete button.
3. `researchfacility_id` was absent from the config entirely, although both
   create DTOs require it.
4. `forceInputsDeactivated: true` (`backoffice-module-config.ts`) rendered the
   backoffice "deactivate inputs" checkbox **checked and disabled** — the
   control in the issue's video that cannot be activated. It was display-only:
   it never wrote `inputs_deactivated` into the stored config, so what actually
   kept the module read-only was gate 1, not this flag.

## Delivered

### The form

`researchfacility_id` becomes a select whose options come from the year's
factor catalog (`GET /factors/{det}/list?year=`, which already backs the grant
grid, #1980) — the id is an opaque code (`1902` → `SCITAS-GE`), so
`class-subclass-map` cannot label it. Picking a facility mirrors
`researchfacility_name` and `use_unit` back from the factor through
`ModuleForm`'s existing `factorValueFieldIds` mechanism (the same one
Buildings-combustion uses for `unit`). Animal facilities adds a
`researchfacility_type` subkind select, filtered to the picked facility by
`class-subclass-map` and translated through its existing `optionLabelKey`.

**Label bug found in manual testing (2026-08-24).** The first pass shipped a
dropdown of raw unit codes. Root cause was not the option source but
`ModuleForm.getFilteredOptions`, which relabels every option from the submodule
taxonomy (`taxoChildMap.get(opt.value).label`). `ModuleHandlerService.get_taxonomy`
labels a kind node with `handler.kind_label_field` when set and falls back to the
kind value otherwise — and **no handler in the codebase set it**, so RF nodes were
labelled with `researchfacility_id` and overwrote the names. Fixed at the source:
both RF handlers now declare `kind_label_field = "researchfacility_name"`. That
also fixes the label wherever else the taxonomy feeds display (table inline
select, print). Regression test:
`backend/tests/unit/services/test_research_facilities_taxonomy_labels.py`.

### Per-unit bounds on `use`

`use` measures a different quantity per platform, named by the factor's
`use_unit`: a share of the platform (`%`, 1 facility), machine time (`hours`, 5),
spend (`CHF`, 80), or animal housings (`housings`). The factor carries no
min/max, so the bounds are hardcoded and mirrored on both sides —
`USE_BOUNDS` in `modules/research_facilities/data_entries.py` (enforced by a
`model_validator` on all four create/update DTOs) and `conditionalBounds` on the
`use` field in the module config, resolved by `ModuleForm.getBounds`:

| `use_unit` | bound              |
| ---------- | ------------------ |
| `%`        | 0–100              |
| `hours`    | 0–8760             |
| `CHF`      | ≥ 0, no ceiling    |
| `housings` | ≥ 0, whole numbers |

Violations are rejected, not clamped — `use` divides straight into the
platform's footprint, so 150% of CAM-GE would claim one and a half times its
whole emissions. A `use_unit` absent from the table is unbounded above:
another institution may use one this deployment has never seen. That is the
accepted cost of hardcoding over deriving the cap from the factor's
`total_use`.

`conditionalBounds` mirrors the existing `conditionalVisibility` /
`conditionalRatio` / `conditionalOptions` family on `ModuleField` rather than
introducing a new shape.

`class-subclass-map` is **not** replaced — it still backs the animal type
subkind select. It cannot back the facility select: it returns
`dict[str, list[str]]` keyed on `handler.kind_field`, and for RF that field is
`researchfacility_id` (an opaque code) while the name lives in a separate
classification key, so the response shape has nowhere to carry a label. Every
other module is unaffected because its kind value already _is_ its label
("Milling machine"). The catalog is cached in the factors store on the same
`submodule:year` key and 60s TTL as the subclass map, so a second select over
the same submodule reuses one fetch.

Reuse over new machinery: `useEquipmentClassOptions` gained one optional
`classLabelField`, `ModuleField` one optional `optionsLabelField`, and the
factors store one alternative option source. No new composable, no new
endpoint, no `ModuleForm` branch beyond the per-module `factorValueFieldIds`
entry every other module already has.

`use_unit` is **read-only in the form and no longer inline-editable** in the
table. The emission formula returns `None` unless the entry's unit
string-equals the factor's, and since #2050 J1 that raises — a typed unit is a
guaranteed 422. This diverges from #951's "Unit modifiable" line for this
module; Buildings-combustion is the in-repo precedent for a factor-mirrored
unit, and static config is a layout concern AND-ed with policy, so no matrix or
backend change was needed.

### Off by default, switchable in the backoffice

The per-submodule `inputs_deactivated` flag already hides the form, disables
the table, and shows the deactivated notice. Research Facilities now defaults
to it:

- `generate_default_year_config()` emits `inputs_deactivated` and
  `csv_deactivated` per submodule, both `True` for `research_facilities` (70)
  and `animal_facilities` (71) via `MANUAL_INPUT_OFF_BY_DEFAULT`.
  `csv_deactivated` matters because `hasModuleUpload` (`ModuleTable.vue`)
  shares the `hideIn.form` predicate — un-hiding the form would otherwise also
  expose the CSV toolbar, which RF never had.
- **No data migration.** `generate_default_year_config` only covers years
  created from now on, so an already-configured year resolves the flags to
  `false`. Decided 2026-08-24: the backoffice Data Management screen is the
  designed interface for this setting, and writing admin-owned config from a
  migration is the wrong tool — EPFL flips the two checkboxes in prod instead.
  The consequence to plan for: on deploy, Research Facilities shows the
  manual-input form and the CSV toolbar on every already-configured year until
  that is done.
- `forceInputsDeactivated` is gone — from the two RF entries, from the
  `SubmoduleConfig` type, and from `SubmoduleItem.vue`. The checkbox is now a
  real, editable control.

### The switch fails closed

`inputs_deactivated` was a pure UI affordance: no write route consulted it, for
any module, so an API client could write to a submodule the backoffice had
closed. `CarbonReportModuleWorkflow.create/update/delete` now reject with
`403 {"code": "INPUTS_DEACTIVATED"}`, after the RBAC gate and beside the #951
policy check. Two carve-outs:

- **Plan and grant reports are exempt** (`CarbonReport.carbon_project_id is not
None`) — the same signal the frontend uses. Their rows are the user's own
  scenario, not calculator data entry, and the Project Grant RF grid must keep
  working while the calculator switch is off.
- **A note-only PATCH is exempt** (`set(item_data) <= ALWAYS_WRITABLE_FIELDS`).
  RF ships `hasTableNote: true`, so the note button renders even with no form
  and is the one write affordance RF users have today; annotation is not data
  entry. `isModuleNoteDisabled` already ignores the table-level disable, so the
  frontend side needed nothing.

A missing `year_configuration` row, module key, or submodule key resolves to
"not deactivated" — the default `SubmoduleConfig` declares, not a swallowed
error.

### Dead code removed

`SubModuleSection.vue` carried a second `<q-card>` branch rendering an
**ungated** `<module-form>` (no `isInputDeactivated`, no notice), reachable only
when `collapsible === false` — a prop no caller anywhere passes. Branch and prop
deleted rather than duplicating the gate into them.

## Files

**Frontend** — `constant/module-config/research-facilities.ts`,
`constant/moduleConfig.ts`, `constant/backoffice-module-config.ts`,
`api/factors.ts`, `stores/factors.ts`, `utils/factorOptions.ts` (new),
`composables/useEquipmentClassOptions.ts`,
`components/organisms/module/ModuleForm.vue`,
`components/organisms/module/SubModuleSection.vue`,
`components/molecules/data-management/SubmoduleItem.vue`,
`i18n/research_facilities.ts`

**Backend** — `services/year_config_service.py`,
`workflows/carbon_report_module.py`

## Tests

- `backend/tests/unit/services/test_year_config_service.py` — RF submodules
  default deactivated, every other submodule does not.
- `backend/tests/unit/workflows/test_carbon_report_module_permissions.py` —
  create and delete 403 `INPUTS_DEACTIVATED`; a note-only PATCH still saves; a
  plan report ignores the flag.
- `frontend/tests/unit/factorOptions.spec.ts` — `toClassOptions` labels by name,
  keeps the opaque id as the value, sorts by label, offers a multi-type facility
  once, and drops rows missing either field.

**Not covered by tests:** the runtime form path — pick a facility → name and
unit mirror in → the animal type list filters to that facility → create returns 201. No spec exercises `useEquipmentClassOptions` with `classLabelField`, and a
module-config assertion is not possible in this harness (see below). Needs the
manual pass in the plan's verification steps.

**Worth knowing for anyone running migrations in this repo:** `backend/.env`
points `DB_URL` at the shared dev database, and pydantic resolves the dotenv
over an inline environment variable — so `make db-migrate` / `make db-drop`
from a checkout target dev, not localhost.

`toClassOptions` was extracted to `utils/factorOptions.ts` because a unit spec
cannot import a module config: `utils/number.ts` pulls in `boot/i18n`, whose
`import.meta.glob` has no Node equivalent in this harness. The store-free-leaf
shape mirrors `utils/dataEntryPolicy.ts`.

## Folded in: naming the filter that emptied an ingest

Surfaced while testing this branch. A 2026 research-facilities API sync failed
with _"No research facilities rows passed validation — all rows were filtered
out during transform"_, which reads like a validation bug. It was not: the
datasource returned 9484 rows, **all dated 2025**. The message could not
distinguish "this year is not published yet" from "the datasource changed
shape", and telling them apart took a one-off probe against Tableau.

`transform_data` had six independent `continue` filters and logged only the
total kept. Now each filter tallies its own reason and the outcome names them:

```
Nothing to import: none of the 9484 research facilities row(s) fetched are in
scope — 8916 row(s) are dated a different year than 2026; 568 row(s) are not
internal billing (client_type is not INTERNE)
```

The mechanism lives on `BaseTableauApiProvider` (`DROP_REASON_MESSAGES`,
`EXPECTED_EMPTY_DROP_REASONS`, `drop_reasons`), so the headcount and
professional-travel providers can adopt it without new plumbing; until they
declare reasons they behave exactly as before.

**WARNING vs ERROR.** An empty transform explained _entirely_ by routine
exclusions — external billing, a year not yet published — finishes as
`IngestionResult.WARNING`. Anything else still raises: a flipped sign
convention would empty the ingest just as completely, and that is a fault.
Routine reasons cannot launder an anomaly into a warning — the check is that
every drop reason is expected, not merely the dominant one.

Previously imported entries are left untouched on the warning path: an empty
fetch is not evidence that an earlier sync's rows are stale.

Tests: `backend/tests/unit/services/data_ingestion/test_research_facilities_drop_reasons.py`
(7 cases, including the reported 2026 incident and the sign-flip that must stay
an error).

## Known gaps

- **No uniqueness constraint** on RF entries — the same facility can be added
  twice and double-counted. The generic `check-unique` endpoint exists if
  product wants it; no other module wires it, so neither does this.
- `backend/INPUT_DATA/researchfacilities_animals_template.csv` ships `mice` as
  the sample `researchfacility_type`, but `resolve_animal_facilities` accepts
  only `rodent`/`fish` and raises otherwise. The frontend copy of the template
  says `rodent`. Pre-existing, unrelated to this change, worth its own issue.
- "Modularity for other institutions" needs no new axis here: there is no
  tenant model, and per-year `inputs_deactivated` is the codebase's existing
  per-institution config surface (one deployment per institution, per
  `frontend/src/config/runtime.ts`).
