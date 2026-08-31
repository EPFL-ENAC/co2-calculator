---
status: delivered
issue: 2441
last_updated: 2026-08-28
summary: 'The Results IT-focus waffle claimed ~90% IT share for a unit whose real share was ~9%: the persisted stat divided validated IT kg by the validated totals of only the four IT source modules instead of all modules. Renamed the stat to percentage_of_validated_total and made its denominator the validated total across all buckets. Also fixed the IT-focus total big number rounding (1.2 t rendered as "1" while its parts showed 0.8 + 0.4) by formatting it with up to one decimal.'
---

# IT focus graph wrong % calculation (#2441)

## Symptom

A unit with 11.5 t total footprint and ~1.2 t IT footprint saw "90%" as the
IT share, and the waffle almost fully coloured. Separately, the IT total big
number read "1 t" while its category parts read 0.8 + 0.4.

## Root cause

`derive_report_sections` (`backend/app/utils/report_stats.py`) computed
`percentage_of_source_modules` as validated IT kg ÷ the validated totals of
only the four IT source buckets (equipment, purchases, research facilities,
cloud & AI). A unit whose four source modules are mostly IT therefore showed
a near-100% share regardless of buildings, travel, process emissions, etc.

The "1 t vs 0.8 + 0.4" mismatch was display rounding: `formatTonnesCO2`
renders one decimal below 1 t but zero decimals at ≥ 1 t, so exactly 1.2
rendered as "1".

## Fix

- Denominator is now the validated total across **all** buckets
  (`sum of buckets[key].total_kg for key in validated_buckets`), matching the
  Results headline total and the existing hint "Based on validated categories
  only". Numerator (validated IT kg) unchanged.
- The stat is renamed `percentage_of_validated_total`; the old name would
  have lied about the new semantics. Renamed end-to-end: `report_stats.py`,
  `frontend/src/utils/emissionStatsAdapter.ts`, `frontend/src/stores/modules.ts`,
  `ItFocusSection.vue`, `ItFocusBreakdownChart.vue`, and the simulator
  integration mocks.
- `ItFocusSection.vue` formats the IT total with up to one decimal
  (`nOrDash` with `maximumFractionDigits: 1`) so the total visibly equals the
  sum of its parts.

## Operational note

The percentage lives in persisted `carbon_report.stats`; existing reports
show 0% (field absent) until a backoffice recompute refreshes their stats.
