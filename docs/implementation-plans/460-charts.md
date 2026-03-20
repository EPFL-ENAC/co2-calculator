# Implementation Plan: Reporting Aggregated Charts (#460)

## Objective

Implement two charts in the reporting page using already aggregated unit data:

1. Unit Carbon Footprint (`tCO2-eq`)
2. Carbon Footprint per FTE (`tCO2-eq/FTE`)

Both charts must react to the same filter state as the units table.

## Final Architecture

- Data source: existing `GET /backoffice/units` endpoint
- Backend extension: expose `emission_breakdown` aggregated from module `stats.by_emission_type`
- Frontend integration: reuse existing result-page chart components
  (`ModuleCarbonFootprintChart` and `CarbonFootPrintPerPersonChart`)
  using `emission_breakdown`
- No new endpoint introduced

## API Contract

- Endpoint: `GET /backoffice/units`
- Request filters (unchanged):
  - `years`
  - `path_lvl2`
  - `path_lvl3`
  - `path_lvl4`
  - `completion_status`
  - `search`, `modules`, `page`, `page_size`
- Response fields used by charts:
  - `emission_breakdown.module_breakdown`
  - `emission_breakdown.additional_breakdown`
  - `emission_breakdown.per_person_breakdown`
  - `emission_breakdown.validated_categories`
  - `emission_breakdown.total_tonnes_co2eq`
  - `emission_breakdown.total_fte`

## Implementation Status

### Backend

- [x] Build aggregated chart rows from `CarbonReportModule.stats.by_emission_type`
      for current reporting result set
- [x] Derive chart payload with backend helper `build_chart_breakdown`
- [x] Expose `emission_breakdown` in `/backoffice/units` response schema

### Frontend

- [x] Extend backoffice units response typing with `emission_breakdown`
- [x] Reuse result-page components in reporting page:
  - `ModuleCarbonFootprintChart`
  - `CarbonFootPrintPerPersonChart`
- [x] Bind reused charts to `units.emission_breakdown`

## Validation Checklist

- [ ] Compare chart values against aggregated emission type totals from module stats
- [ ] Verify per-person chart behavior for headcount validated/non-validated cases
- [ ] Verify year and hierarchy filters update table + charts together
- [ ] Verify completion filter updates table + charts together
- [ ] Verify chart rendering when filtered result set is empty

## Non-Goals

- No dedicated charts endpoint
- No additional pagination strategy for charts in this iteration

## Risks / Follow-ups

- Aggregation currently uses current page report IDs (page-scoped charts); if full filtered
  aggregation is required across all pages, add a dedicated aggregate query in follow-up
- Missing or stale module stats would directly impact chart accuracy
