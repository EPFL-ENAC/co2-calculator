---
status: delivered
issue: 2091
last_updated: 2026-08-19
title: "Emission type resolution fails hard, and is documented"
summary: "Every module invented its own answer for a factor CSV value the taxonomy did not know: two resolvers raised, four returned None, and four walked up the tree onto an intermediate node — which double-counts, because an intermediate node already sums its children. Measured against the real INPUT_DATA CSVs, 877 of 18,977 factor rows resolved onto a node with children; 21 of those were genuine degradations (20 headcount, 1 centralized purchase) and 16 external-AI rows collapsed into provider_others, leaving the AI breakdown chart as a single bucket. This plan makes all eight runtime resolvers raise EmissionTypeResolutionError naming the offending value, adds a funnel guard rejecting any runtime resolution onto a node with children, escalates the factor-CSV provider from skip-row to abort-upload for emission-type failures only, adds the nine missing taxonomy leaves the real CSVs need, and ships a reference page with mermaid diagrams plus a pre-upload audit script. All 15 shipped factor CSVs resolve clean afterwards."
---

# #2091 — Emission type resolution fails hard

## Why

A factor filed on the wrong node produces a total that renders, looks
complete, and is wrong. That is the failure mode the guardrails rank worst,
and the resolution layer had four separate ways of producing it.

The trigger: a data manager renamed a process-emissions category from `CO2`
to `Carbon dioxide (CO2)` and the upload broke loudly — because process
emissions happened to be one of the modules that returned `None`. The same
rename in headcount would have degraded silently onto a parent node instead.

## What was actually wrong

Measured, not assumed — every `INPUT_DATA/*factors*.csv` run through
`resolve_factor_emission_type`:

| Source                                             | Rows on a node with children | Verdict                                                                                                                                         |
| -------------------------------------------------- | ---------------------------: | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `building_rooms`, `travel_planes`, `travel_trains` |                          856 | Declared. `FACTOR_TO_EMISSION_TYPES` files one factor at an intermediate node on purpose; the leaf is a data-entry-time decision.               |
| `headcount_member` + `headcount_students`          |                           20 | **Degraded.** `'domestic waste'` never matched `waste__incineration__domestic_waste` — the resolver lowercased but never normalised separators. |
| `purchases_centralized`                            |                            1 | **Degraded.** `'Liquid Nitrogen'` → `liquid_nitrogen`, map key was `ln2`.                                                                       |

Plus a separate silent collapse the strictness surfaced: 16 of 19
`external_ai_factors.csv` rows fell into `provider_others`, because only
`Mistral AI` — the one vendor with no product prefix and no parenthesis —
happened to match a map key.

Inconsistency across the ten resolvers, before:

- **raised:** `resolve_animal_facilities`, `_heating_leaf_for_factor`
- **returned `None`:** `resolve_process_emissions`, `resolve_clouds`,
  `resolve_plane`, `resolve_train`, `resolve_headcount_factor` (some inputs)
- **degraded to a parent:** `resolve_headcount_factor`, `resolve_combustion`,
  `resolve_purchases_centralized`, `resolve_building_rooms`
- **degraded to a misc bucket:** `resolve_ai` → `provider_others`

`None` then reached the factor provider, which recorded a row error, skipped
the row, committed every other row, and finished `IngestionResult.WARNING`.

## What shipped

1. **`EmissionTypeResolutionError`** in `taxonomy.py` — a distinct type so
   the provider can escalate it without swallowing ordinary row errors.
2. **`canonical_token`** — separator-only canonicalisation
   (`"organic waste (lawn)"` → `organic_waste_lawn`, which is how the
   taxonomy already spells it). It never chooses a node.
3. **All eight runtime resolvers raise**, naming the value that failed.
   `resolve_research_facilities` keeps its default: the IT list is an
   allow-list, so "not in it" is a real answer onto a childless leaf.
4. **`provider_others` is reachable only by naming it.** An unknown vendor
   now raises rather than disappearing into a bucket nobody audits.
5. **Funnel guard** in `resolve_factor_emission_type`: a runtime resolution
   onto a node with children raises. `FACTOR_TO_EMISSION_TYPES` returns
   before it, so the three declared intermediates stay legal.
6. **Upload aborts, not skips.** `_process_row` re-raises
   `EmissionTypeResolutionError`; `process_csv_in_batches` already rolls
   back on any exception, so no partial commit survives. Malformed values
   keep skip-and-continue — the escalation is scoped to emission types.
7. **Nine new leaves**, appended and never renumbered:
   `waste__incineration__incineration_waste_bio_chem_ani`,
   `waste__recycling__{batteries,neon_tubes,chemical_waste}`,
   `process_emissions__{hfcs,perfluorinated_compounds,fluorinated_ethers,perfluoropolyethers}`
   (each F-gas family its own leaf, no longer sharing `refrigerants`),
   `external__ai__provider_{github,microsoft}`.
8. **Reference page** with mermaid diagrams:
   [Emission Type Resolution](../backend/emission-type-resolution.md).
9. **`scripts/audit_emission_type_resolution.py`** — dry-runs a directory of
   factor CSVs, exits non-zero on anything that would abort an upload.

## Divergence from the issue as written

#2091 proposes the opposite: accept the factor, show a warning, and route
unknown values to a `module_submodule_others` fallback bucket.

That is the behaviour being removed, and it is the behaviour that hid this.
The issue's own stated goal — "we're sure we don't miss anything, as was the
case for rodent" — depends on somebody reading a warning; the existing
`IngestionResult.WARNING` _is_ that warning, and nobody read it for the 21
degraded rows in the shipped CSVs. A rejected upload naming the exact
unmapped value achieves the goal the proposal was reaching for, and the
guardrails forbid the misc bucket outright.

Raised for the stakeholders to confirm, not decided unilaterally.

## Deliberately not done

- **SF6 and NF3 still map to `process_emissions__refrigerants`.** They are
  not refrigerants either, but they were outside the split request. One-line
  change when wanted.
- **No data migration.** Existing rows under the old ids are not rebased;
  the lead is dropping the database, so overlapping data is acceptable here.
- **`processemissions_data.csv` uses `category=Refrigerant` while
  `processemissions_factors.csv` uses `category=Hydrofluorocarbons (HFCs)`.**
  Strategy A matches factors on classification `category`, so these two do
  not meet. Pre-existing, unrelated to emission types, needs its own issue.
- **The four F-gas group-header rows** (`category` set, `subcategory` and
  `ef_kg_co2eq_per_unit` empty) still skip on validation. They carry no
  factor value, so skipping them is correct.

## Tests

- `tests/unit/modules/test_emission_type_fail_hard.py` — every resolver's
  unmapped value raises and names itself; the 13 real headcount spellings
  resolve to childless leaves; the AI product-name spellings resolve
  distinctly; the funnel guard rejects an intermediate and exempts the
  declared ones.
- `tests/unit/services/data_ingestion/test_base_factor_csv_provider.py` —
  an unmapped emission type propagates with its row number and records
  **no** skipped row; a malformed value still skips.
- Updated to the new contract: `test_process_emissions_emissions.py`,
  `test_plane_cabin_class.py`, `test_building_rooms_resolver.py`.
