---
status: proposed
issue: 404
last_updated: 2026-07-15
title: "Simulator Module"
summary: "Standalone module letting any authenticated user project a research project's (or single category's) carbon footprint by reusing reference-year annual unit data, without writing back to the data-entry modules."
---

# Simulator Module

## Problem/Purpose

Researchers and lab managers currently have no way to estimate a project's carbon footprint before, during, or after execution without manually re-deriving numbers outside the tool. The Simulator module addresses this by reusing already-computed annual unit data from a chosen reference year and letting the user project it forward (or adjust it) per module, per year, without touching the underlying data-entry records.

Goals:

- Enable pre-, during-, and post-project carbon estimation.
- Reuse existing annual unit data from the main data-entry interface (read-only reuse — no write-back).
- Support individual use with optional lab-level sharing.
- Produce exportable reports (PDF, CSV) with configurable charts.

Non-goal: this plan does not change the Calculator/data-entry modules themselves; the Simulator only reads their reference-year outputs.

## Design

### Access & Permissions

- Accessible to all authenticated users.
- Each user sees only their own workspace by default (individual scope).
- A simulation can optionally be shared with the lab via a "Share with lab" toggle.
- Data entered in the Simulator is never pushed back to the main data-entry interface — strictly one-directional read of reference-year data.

### Title Box

- Page title/subtitle (FR/EN copy already drafted by product — not reproduced here, pull from Figma/spec doc at implementation time).
- Descriptive text plus a tooltip linking to the methodology docs.

### Project Information Box

- Text field: "Project name".
- Year selection: Start Year / End Year (4-digit numbers). Once both are filled, one section per year in `[Start Year, End Year]` renders below.
- Visibility checkbox: user-only vs. all lab members (this is the "Share with lab" toggle from Access & Permissions).

### Per-Year Section, Module Behavior

Each year in the project's range gets its own section containing:

- A "Reference year" dropdown, constrained to years that are open in the Calculator. All factors and data used for that simulation year are sourced from the selected reference year.
- The full set of modules, in the same order as they appear in the Calculator.
- Every module has an Active checkbox (default on). Unchecking a module excludes it from sums, graphs, and results for that year.

Modules fall into three behavior types:

| Type                     | Behavior                                                                                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1. Manual entry          | User enters values directly; no reference-year default.                                                                                                            |
| 2. Pre-filled + % slider | Defaults to reference-year data; user can dial a per-row % of the reference year; also exposes the full input form, identical to the Calculator, for direct edits. |
| 3. Empty by default      | No pre-fill; input form identical to the Calculator.                                                                                                               |

### Per-Module Specifics

| Module                 | Type                   | Behavior                                                                                                                                                                                                                                               |
| ---------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Headcount              | 1. Manual              | Manual FTE/year entry per SIUS-code category.                                                                                                                                                                                                          |
| Travel                 | 3. Empty               | Empty by default; input form identical to the Calculator, except the traveler dropdown offers categories (internal / external EPFL / internal EPFL) instead of headcount names.                                                                        |
| Process Emissions      | 2. Pre-filled + slider | Prefilled table: columns "emitted Gas", "subcategory", "Reference year kg-CO2-eq" (from reference year), plus two calculated columns "estimated kg-CO2-eq" and "% of reference year" (per-row slider). Also exposes a Calculator-identical input form. |
| Buildings              | 2. Pre-filled + slider | Prefilled table with two calculated columns as % of last year, plus a Calculator-identical input form.                                                                                                                                                 |
| Equipments             | 2. Pre-filled + slider | Prefilled table with two calculated columns as % of last year, plus a Calculator-identical input form. Scientific/IT and Other Equipment may be one table or split — implementer's choice.                                                             |
| Purchases              | 1. Manual              | Manual CHF total entries, as either (a) the sum of each submodule's total, or (b) a single global budget. Exactly one of the two must be filled — submodule totals and global budget are mutually exclusive.                                           |
| Research Facilities    | 2. Pre-filled + slider | Prefilled from reference year, plus a Calculator-identical input form.                                                                                                                                                                                 |
| External Clouds and AI | 2. Pre-filled + slider | Prefilled from reference year, plus a Calculator-identical input form.                                                                                                                                                                                 |

### Simulation Results

- Main chart: "{Project Name} Carbon Footprint".
- Export: PDF report, with configurable charts. CSV export is also a stated goal (see Open Questions — export format scope is not fully pinned down per-module).

## Open Questions

This epic is still in definition (label "issue in definition" on #1555). The following are explicitly unresolved and must be settled before/during implementation, not assumed:

- **Front/backend split**: #1555's own body says "let's make these their own issues / but it's not split front/backend?" — whether this plan (or its sub-issues) will be split into separate frontend/backend tickets is undecided.
- **Relationship to #1556**: resolved — #1556 is the backend slice, specified in [1556-simulation-plan-backend.md](1556-simulation-plan-backend.md).
- **Per-module issue breakout**: the per-module specs above (Headcount, Travel, Process Emissions, Buildings, Equipments, Purchases, Research Facilities, External Clouds & AI) may each become their own issue. This plan treats them as one epic for now; re-split Steps below if/when that happens.
- **Data model / API shapes**: decided for the backend — see [1556-simulation-plan-backend.md](1556-simulation-plan-backend.md). Plan-years are ordinary `CarbonReport` rows under a `Simulator_Plan` project; entries reuse the Calculator `data_entries` pipeline; factors resolve from the reference year. PR #1804 shipped the plan-CRUD esquisse (API, service, repo, model fields, Plan UI shell).
- **Design source**: a Figma design and a separate spec doc are referenced in #1555 but not accessible here — implementers must pull current specifics (exact copy, layout, calculated-column formulas) from those sources before building, since they may have moved on since this plan was drafted.
- **CSV export scope**: the Goals section mentions CSV export alongside PDF, but the Simulation Results section only names "Export PDF Report" explicitly — confirm whether CSV is in scope for the first cut.

## Steps

### Phase 0 — Decide open questions

- [ ] Confirm with product/#1555 owner whether front/backend will be split into separate issues, and if so, how.
- [x] Clarify #1556's actual scope against this plan; either merge its content here or explicitly delineate the backend-only slice. → backend slice delineated in [1556-simulation-plan-backend.md](1556-simulation-plan-backend.md).
- [ ] Decide whether per-module specs get split into their own issues; if yes, link them back to this plan and #404.
- [ ] Pull current Figma + spec doc content to confirm copy, layout, and any calculated-column formulas not fully specified above (e.g. exact "% of last year" formula for Buildings/Equipments).
- [ ] Confirm CSV export is in scope for v1, or defer it explicitly.

### Phase 1 — Scaffolding

- [ ] Define data model for a Simulation (project name, start/end year, visibility, per-year reference-year selection, per-module active flags) — once Phase 0 unblocks the shape.
- [ ] Stand up the Simulator route/page shell: Title Box, Project Information Box, empty per-year section scaffold.
- [ ] Implement access control: individual-scope by default, "Share with lab" toggle, no write-back to data-entry modules.
- [ ] Wire read-only reuse of reference-year annual unit data (reference-year dropdown constrained to years open in the Calculator).

### Phase 2 — Per-module implementation

- [ ] Headcount: manual FTE/year entry per SIUS-code category.
- [ ] Travel: empty-by-default, Calculator-identical form.
- [ ] Process Emissions: prefilled table + % slider + Calculator-identical form.
- [ ] Buildings: prefilled table + % slider + Calculator-identical form.
- [ ] Equipments: prefilled table + % slider + Calculator-identical form (decide one table vs. split at implementation time).
- [ ] Purchases: manual entry, submodule totals vs. global budget (mutually exclusive), with validation enforcing exactly one is filled.
- [ ] Research Facilities: prefilled + Calculator-identical form.
- [ ] External Clouds and AI: prefilled + Calculator-identical form.
- [ ] Per-module Active checkbox wired into sums/graphs/results exclusion logic.

### Phase 3 — Results & export

- [ ] Main chart "{Project Name} Carbon Footprint", aggregating across active modules/years.
- [ ] PDF export with configurable charts.
- [ ] CSV export (pending Phase 0 scope decision).
