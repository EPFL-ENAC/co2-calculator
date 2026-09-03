---
status: delivered
issue: 2613
last_updated: 2026-09-01
summary: Seed en+fr labels for enum-key classification values, serve every label backend-side, delete the frontend $te/optionLabelKey/optionLabelPrefix fallback machinery.
---

# 2613 — backend-owned labels for enum-key classification fields

Endgame of #2401: after this branch, the frontend renders backend labels for
every factor-sourced classification value. The only client-side option labels
left are professional-travel cabin classes (static form enums, kept by
maintainer decision).

## Why now

- energy_combustion fuels (`natural_gas`, …) were translated ONLY client-side:
  French filter/sort on the energy table matched English, and English filter
  didn't even match the displayed label (`Natural gas` vs `natural_gas`).
- Five fields had two label sources (backend translation table for matching,
  frontend i18n for display) — the drift failure mode #2401 exists to kill.

## Backend

- **Seed migration** (`seed_enum_label_translations`, same pattern as the sius
  seed `3b5609f893f4`): en+fr rows for
  - `name` (energy_combustion fuels ×7, wording from `i18n/buildings.ts`),
  - `room_type` (×6, wording from `buildings-room-type-*`),
  - `researchfacility_type` (fish/rodent),
  - `service_type` (storage/compute/virtualisation — virtualisation covers
    legacy entries; the current catalog has no factor for it).
- **Handlers** declare `translated_code_fields`: energy_combustion `("name",)`,
  buildings rooms `("energy_type", "room_type")`, RF animal
  `("researchfacility_type",)`, external clouds `("service_type",)`.
  The repo layer (filter, localized sort, row labels) already handles the
  shape in every language — no repo change.
- **Taxonomy builder** (`module_handler_service`):
  - fetches translation rows for `translated_code_fields` in EVERY language
    (was: only `lang != en`), so fuel/room-type nodes carry "Natural gas",
    not the slug, in English too;
  - handlers with `kind_field=None` and `translated_code_fields` (headcount
    member, planner_headcount) get vocabulary children built from the
    translation table — the sius dropdown/planner grid label source.
- **Breakdown enrichment** (`enrich_breakdown_with_labels`): also consults the
  translation table in English when the group field is a translated code field
  (animal-facility bars grouped by `researchfacility_type`).

## Not seeded (deliberate)

- `process_emissions.category/subcategory`: CSV values are real English text —
  already the self-labeling shape, `_fr` CSV columns cover French. The
  frontend `optionLabelKey` slugs (`co2`, `refrigerants`, …) matched nothing
  in the current catalog: dead code, deleted.
- `usage_type` (external_ai): self-labeling; `usage_type_fr` CSV wording still
  parked with the maintainer.
- Known collision non-risk: `purchases_centralized.kind_field == "name"` shares
  the `name` field namespace with fuels, but a purchase would have to be
  literally named `natural_gas` to collide — accepted.

## Frontend

- `optionLabelKey` and `optionLabelPrefix` removed from `moduleConfig` and all
  render paths (ModuleTable, ModuleForm, ModuleInlineSelect, printTable);
  `optionLabelsAreKeys` survives ONLY for travel cabin classes.
- New `optionLabelsFromTaxonomy` config flag for static-vocab selects whose
  labels now come from the loaded taxonomy tree: headcount `sius_code`,
  buildings `room_type`. Taxonomy label maps flatten kind AND subkind nodes.
- All `$te(node.name)` / `$te(opt.value)` fallback branches deleted — nodes
  render `node.label`, rows render backend `labels`.
- Planner headcount (rows, print) reads sius labels from the planner_headcount
  taxonomy vocabulary; the student row keeps its own UI i18n key.
- Deleted: `i18n/headcount_factor.ts` and the dead label keys (fuels,
  room types, RF types, storage/compute/virtualisation, process category
  slugs).

## Delivery checklist

- [x] seed migration + handler declarations
- [x] taxonomy builder: en labels + vocabulary children
- [x] breakdown enrichment en path
- [x] backend tests (fuel filter/sort en+fr, taxonomy en labels, member vocab, RF-type breakdown)
- [x] frontend flip + machinery deletion + CT coverage
- [x] lint + type-check green
