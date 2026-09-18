---
status: delivered
issue: 2749
last_updated: 2026-09-18
title: "Planner equipment: global percentage in the Detailed per Year sections"
summary: "The equipment 'Planning mode' toggle (manual entry per line vs one global percentage of the reference year, #1981) existed only in the Project Grant section. It is now offered in every Detailed per Year section too; the backend route behind it no longer rejects non-grant plan reports. Budgets stay grant-only. Follow-up: global mode at 0% is now the prefill default, so equipment no longer copies every reference line."
---

# Planner equipment: global percentage in the year sections (#2749)

## Symptom

In a plan with `Detailed per Year` sections, the Equipment module showed the
prefilled reference-year table with a percentage per line, but not the
"Global percentage" option the Project Grant section offers. The
maintainers clarified in the issue that this is a parity gap, not a
regression: #1981 shipped the toggle grant-only (see
[1976-grant-proposal-mode](./1976-grant-proposal-mode.md)), and the
ask is to offer both modes in every section.

## Change

**Backend** — `PATCH /carbon-reports/{id}/modules/{module_type_id}/reference-percentage`
went through `_require_grant_report_edit`, which 409s on any report with
`is_grant = false`. A new `_require_plan_report_edit` keeps the same
checks (report exists, unit access, plan-edit scope) without the grant
gate, and the reference-percentage route uses it. The budget routes keep
the grant gate: budgets are a grant concept (#1978).

No model, schema or migration change. The mode is view state, as it
already was for the grant section; the per-entry
`percentage_of_reference_year` writes were already legal on year reports
(`PLANNER_SNAPSHOT_WRITABLE_FIELDS`).

**Frontend** — `PlannerYearSection.vue`: the toggle block is gated on the
module alone (`isEquipmentModeModule`) instead of `is_grant && Equipment`.
Inside global mode, the module-level budget field (and its separator)
stays behind `yearData.is_grant`. The switch-confirmation dialog gets
year-section wording (`planner_equipment_switch_to_global_year_message`,
`planner_equipment_switch_to_per_line_year_message`) that does not mention
budgets. Everything else — the reference total, the planned result, the
locked per-row sliders, the table remount after an apply, the deletion of
hand-added rows on a confirmed switch — is shared as is.

## Follow-up: global percentage is the prefill default

Every new grant or year section copied the whole reference-year equipment
module line by line, though one global percentage is the more natural
starting point. Now the prefill starts equipment in global mode at 0%: one
aggregate line per type, priced from the reference module's stats
([#2783](./2783-equipment-global-percentage-aggregate-line.md)). A
950-line reference module writes 3 rows, not 950.

- **Backend** — `_prefill_reference_modules` gets an equipment arm next to
  headcount's: `CarbonReportModuleService.prefill_equipment_global` empties
  the module and writes the aggregate lines at 0%. Per-line rows only come
  back through the explicit switch (`reset_equipment_to_per_line`).
  `get_applied_percentages` now counts aggregate lines only: per-line rows
  carry `percentage_of_reference_year` too (0 on copy), so a per-line module
  used to reload as global. Making aggregates the default
  exposed two #2783 bugs, fixed here: every recompute deleted an aggregate's
  emission row, and listing one 500'd (aggregates are now kept out of the
  device tables) — see
  [2783](./2783-equipment-global-percentage-aggregate-line.md#backend-change).
- **Frontend** — `PlannerYearSection.vue` re-reads the mode from the module
  stats after a reference-year change, not only on mount: the section stays
  mounted while its equipment is rebuilt in global mode.
- **No backfill** — plan years prefilled before this keep their per-line
  rows until their reference year changes or someone switches mode.

## Tests

- `backend/tests/unit/v1/test_carbon_report.py`: the percentage route
  applies to a report with `is_grant=False` (regression), still applies to
  a grant report, and `_require_grant_report_edit` still 409s.
- `frontend/tests/unit/planner-equipment-mode-year-section.spec.ts`: a
  non-grant section with Equipment expanded renders the two mode labels
  with per-line selected; the grant section keeps them.
- Follow-up, in `test_carbon_report_module_service_reference_percentage.py`:
  `test_prefill_starts_equipment_in_global_mode` (aggregate lines at 0%,
  priced, no per-line copy), `test_per_line_rows_do_not_read_as_global_mode`,
  `test_factor_recalc_keeps_aggregate_priced`,
  `test_device_tables_leave_aggregate_lines_out`; the CT
  spec checks a prefilled section opens in global mode and that a
  reference-year change re-reads the mode.
