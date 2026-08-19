---
status: delivered
issue: 1935
last_updated: 2026-08-19
title: "Centralized purchases: manual input"
summary: "Manual entry for the centralized-purchases submodule. Unit and coef_to_kg are entry-level fields (moved off the factor in #2078); the factor carries only ef_kg_co2eq_per_kg, matched by name. Emission = annual_consumption × coef_to_kg × ef_kg_co2eq_per_kg. Follow-up locked manual input to kg: unit is read-only 'kg', coef_to_kg is forced to 1 and hidden from the form (CSV entries keep their real unit/coef); coefficient label corrected to 'Conversion coefficient to kg'."
---

# Centralized purchases: manual input (#1935)

Backfilled plan. The feature shipped in two PRs plus one follow-up:

1. **#2017** (`5c30b52d0`) — first cut: `unit` and `coef_to_kg` added to the centralized-purchase factor.
2. **#2078** (`818aec4d8`) — decision reversal: `unit` and `coef_to_kg` moved **off the factor and onto the data entry**. The factor keeps only `name` (classification) and `ef_kg_co2eq_per_kg` (value). This is the settled shape.
3. Follow-up (this branch) — locked manual input to kg (coef forced to 1, hidden from the form) and fixed the coefficient label.

## Data shape

- **Entry** (`backend/app/modules/purchase/data_entries.py`, `PurchaseCentralizedHandlerCreate`): `name`, `unit` (free string, e.g. `kg`, `liter`), `annual_consumption`, `coef_to_kg`, `note`. `annual_consumption` and `coef_to_kg` must be non-negative; `unit` has no allow-list.
- **Factor** (`backend/app/modules/purchase/factors.py`): `name` + `ef_kg_co2eq_per_kg`, matched via `kind_field = "name"`.

## Formula

`backend/app/modules/purchase/handlers.py`, `PurchaseCentralizedModuleHandler.resolve_computations`:

```
kg_co2eq = annual_consumption × coef_to_kg × ef_kg_co2eq_per_kg
```

`coef_to_kg` converts the entry's unit to kilograms of product (1 liter of liquid nitrogen = 0.8 kg); the factor's `ef_kg_co2eq_per_kg` then converts kg of product to kg CO₂-eq. The entry's `unit` is display/sort/filter only and never enters the computation. The same contract applies to CSV-ingested entries (`purchases_centralized_data.csv`: `unit_institutional_id, name, unit, annual_consumption, coef_to_kg, note, kg_co2eq`).

## Follow-up: kg-only manual input + label fix

Manual input is deliberately kg-only, so a hand-typed row can never disagree with itself: the user cannot modify `unit` (read-only "kg") nor `coef_to_kg` (forced to 1). CSV/backoffice entries are the path for other units (liter + 0.8 etc.) and keep their real per-entry values.

- `frontend/src/constant/module-config/purchase.ts`: `unit` keeps `default: 'kg'` + `readOnlyWhenFilled: true`; `coef_to_kg` gets `default: 1` + `hideIn: { form: true }` (no `editableInline`), so it disappears from the form but stays a sortable table column. Form ratios back to `1/3` for the three visible fields.
- `frontend/src/components/organisms/module/ModuleForm.vue`: the create-path `init()` now also seeds defaults for form-hidden fields (generic, config-driven), since the visible-field loop skips them and `buildPayload` only sends seeded keys. The edit path returns early after copying `rowData`, so editing an existing CSV row never clobbers its stored coef.
- `frontend/src/i18n/purchase.ts`: `purchase.inputs.coef_to_kg` label corrected from "Conversion coefficient to kg CO₂-eq" to "Conversion coefficient to kg" (fr: "Coefficient de conversion en kg"), since the coefficient converts to kg of product, not kg CO₂-eq.
- `backend/INPUT_DATA/purchases_centralized_factors.csv`: stale pre-#2078 header (`name,unit,coef_to_kg,ef_kg_co2eq_per_kg`) reduced to the current contract (`name,ef_kg_co2eq_per_kg`).

Environments that uploaded centralized factors before #2078 must re-upload them with the 2-column format.
