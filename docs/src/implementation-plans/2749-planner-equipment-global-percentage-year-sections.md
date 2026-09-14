---
status: delivered
issue: 2749
last_updated: 2026-09-14
title: "Planner equipment: global percentage in the Detailed per Year sections"
summary: "The equipment 'Planning mode' toggle (manual entry per line vs one global percentage of the reference year, #1981) existed only in the Project Grant section. It is now offered in every Detailed per Year section too; the backend route behind it no longer rejects non-grant plan reports. Budgets stay grant-only."
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

## Tests

- `backend/tests/unit/v1/test_carbon_report.py`: the percentage route
  applies to a report with `is_grant=False` (regression), still applies to
  a grant report, and `_require_grant_report_edit` still 409s.
- `frontend/tests/unit/planner-equipment-mode-year-section.spec.ts`: a
  non-grant section with Equipment expanded renders the two mode labels
  with per-line selected; the grant section keeps them.
