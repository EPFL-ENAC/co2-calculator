---
status: proposed
issue: 1918
last_updated: 2026-08-19
title: "Planner Purchases: multi-currency input with automated EUR conversion"
summary: "The planner Purchases section (per-category totals and global budget) gets a section-level currency selector mirroring the one already visible in the Calculator purchases module. Stored amounts remain EUR-only (`amount_eur`, no migration): the backend converts a non-EUR input to EUR on write via the existing ECB ExchangeRatesService, and the frontend converts the stored EUR value back into the selected currency for display through a new read-only exchange-rates endpoint. Planner purchase module only; the latent Calculator factor-currency bugs are documented as follow-ups."
---

# Planner Purchases: multi-currency input with automated EUR conversion

Origin: [#1918](https://github.com/EPFL-ENAC/co2-calculator/issues/1918), raised
from [#1861](https://github.com/EPFL-ENAC/co2-calculator/issues/1861) — planner
purchase amounts are hardcoded EUR because the purchase factors are per-EUR;
users need to enter at least CHF, with automated conversion.

The Calculator purchases module already supports this (per-row `currency`
select, backend conversion in `_purchase_formula` via
`ExchangeRatesService.get_exchange_rate_to_eur(year, currency)` — ECB Data
Portal client with an 8h in-process cache,
`app/services/exchange_rates_service.py`). The planner is the gap:
`PlannerPurchaseCreate` / `PlannerPurchaseBudgetCreate`
(`app/modules_planner/purchase/data_entries.py`) carry only
`amount_eur`, the formula is the declarative `amount_eur ×
ef_kg_co2eq_per_eur` (`app/modules_planner/purchase/handlers.py`), and
`PlannerPurchaseRows.vue` hardcodes `suffix="EUR"`.

## Decisions (2026-08-19)

- **Planner purchase module only.** No changes to Calculator purchase or
  external-cloud files; their latent factor-currency bugs are follow-ups
  (below).
- **The DB stays EUR-only — no migration, no rename.** `amount_eur` remains
  the stored key and always holds EUR. Currency is a conversion layer around
  it: converted **to EUR by the backend on write**, converted **from EUR by
  the frontend for display**.
- **One section-level currency selector** in the planner Purchases block
  (applies to both the per-category grid and the global budget input),
  reusing the shared `CURRENCY_OPTIONS` (9 codes) visible in the Calculator
  purchases module.
- **No persistence of the display currency.** The selector defaults to the
  grant `budget_currency` when set, else EUR, on every load. Nothing new is
  stored per entry or per plan.
- **Emission formula untouched.** Since stored amounts are always EUR, the
  declarative `amount_eur × ef_kg_co2eq_per_eur` computation and the derived
  per-EUR planner factors stay exactly as they are. No exchange-rate call in
  the emission path, hence no ECB-availability or future-year concern there.

## Backend

### Write-side conversion (create / update)

- `PlannerPurchaseCreate/Update` and `PlannerPurchaseBudgetCreate/Update`
  (`app/modules_planner/purchase/data_entries.py`) gain a **transient**
  `currency: str | None = None` field: validated (strip/lower, membership in
  the same 9-code set as the Calculator's validators — aud, cad, chf, cny,
  eur, gbp, jpy, sek, usd), interpreted as "the submitted `amount_eur` value
  is denominated in this currency", and **never stored** (excluded before the
  entry data is written). Absent/blank means EUR — every existing client and
  every legacy payload keeps today's semantics bit-for-bit.
- Conversion runs in the planner purchase workflow hook
  (`app/workflows/carbon_report_module.py`, where the XOR /
  one-entry-per-category checks for types 81/82 already run with the report
  in scope): when `currency` is present and ≠ `eur`, replace the amount with
  `amount × ExchangeRatesService().get_exchange_rate_to_eur(year, currency)`
  and drop the `currency` key. The rate year is
  `resolve_factor_year(session, report)` (`app/utils/factor_year.py`, the
  #1922 chain: reference year → unit's latest Calculator year → report
  year) — the same year whose factors price the entry, and a real
  past/current year in every case where factors exist. ECB raises
  `ValueError` for an unknown year/currency; surface it as a 422 on the
  create/patch rather than storing an unconverted amount.
- Responses are unchanged (`amount_eur`, always EUR).

### Read-side rates endpoint (for display)

Display in a non-EUR currency is a calculation from the stored EUR value, so
the frontend needs the rate:

- New read-only route, e.g. `GET /exchange-rates/{year}` (auth-required,
  `app/api/v1/exchange_rates.py`), returning
  `{currency: eur_per_unit}` for the supported codes from
  `ExchangeRatesService` (`get_exchange_rate_to_eur` per code; the 8h class
  cache means at most one ECB fetch per year per pod). A future year with no
  ECB data returns 404; the client then pins the selector to EUR — no
  fallback rates.

### Derived-factors currency guard (in scope: planner purchase module)

`_collect_source_efs` (`app/modules_planner/purchase/derived_factors.py`)
averages the Calculator purchase EFs while ignoring each factor's `currency`
classification — one non-EUR Calculator factor would silently corrupt the
planner per-EUR averages. Guard: skip any source factor whose
`classification["currency"]` is set and ≠ `eur`, with a `logger.warning`,
and fix the module docstring ("both sides are per EUR … nothing is converted
anywhere"). Converting instead (non-inverted units-per-EUR rate) was
rejected: it would make factor uploads depend on ECB availability.

## Frontend

All in `components/organisms/planner/PlannerPurchaseRows.vue` plus one prop
pass-through:

- New props: `budgetCurrency?: string | null` (from
  `PlannerYearSection.vue`, mirroring `PlannerResearchFacilityRows`) and
  `factorYear: number` (the section's existing #1922 factor-year computed —
  the year the backend converts with, so display and write use the same
  rate).
- Section-level `q-select` in the header (options `CURRENCY_OPTIONS`, label
  reuses `planner_budget_currency_label`), initial value
  `budgetCurrency ?? 'eur'`, disabled while a save is in flight. Selecting a
  non-EUR currency fetches `GET /exchange-rates/{factorYear}` once; on 404 or
  error the selector pins back to EUR (no fallback).
- Amount inputs: suffix becomes `:suffix="currencyLabel(currency)"`
  (replaces the hardcoded `suffix="EUR"`); displayed value is
  `amount_eur / eur_per_unit` for a non-EUR selection, raw `amount_eur` for
  EUR.
- Payloads: create/patch send the typed amount as `amount_eur` plus
  `currency: <selected>`; the backend converts and stores EUR. Switching the
  selector is display-only — no re-patching of existing rows, since stored
  values never change denomination.
- i18n: `planner_purchase_amount_label` (`i18n/simulation.ts`) drops the
  hardcoded "(EUR)" — en `Amount`, fr `Montant`; the unit is the dynamic
  suffix. No new keys.
- Round-trip note: editing a CHF-displayed value re-sends the CHF number and
  reconverts; drift is bounded by ECB yearly-average rounding (sub-cent) and
  accepted.

## Tests (adapt existing)

- `backend/tests/unit/modules/test_planner_purchase_schemas.py`: extend the
  existing cases — valid currency normalizes (`"CHF "` → `chf`), invalid
  currency rejected, absent currency means EUR, `currency` never appears in
  the dumped entry data.
- `backend/tests/unit/workflows/test_planner_purchase_exclusivity.py`: the
  XOR/duplicate rules read only `purchase_category` — unaffected; add the
  write-conversion case here (non-EUR create stores the EUR product), with
  `ExchangeRatesService` mocked. No live ECB anywhere in tests.
- `backend/tests/unit/modules/test_planner_purchase_derived_factors.py`:
  pure-function tests unaffected; the non-EUR skip lives in
  `_collect_source_efs`.

## Compatibility and risks

- Existing entries and clients: untouched key, untouched semantics, no
  backfill, no recompute.
- XOR + one-entry-per-category 422s: unaffected (they read only
  `purchase_category`).
- Plan copy and the `percentage_of_reference_year` override path bypass the
  formula and copy EUR values verbatim — unaffected.
- ECB outage: write-side conversion of a non-EUR amount fails with a 422
  (same blast radius the Calculator purchases already accept); EUR entry and
  all display of stored values keep working.
