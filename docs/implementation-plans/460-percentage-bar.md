Implementation plan aggregation box

# Percentagle bar

## Objective

Implement a completion-percentage bar for Backoffice reporting using the existing completion-status pipeline, without introducing a new endpoint.

## Decision

Reuse the existing Backoffice units endpoint and extend server-side filtering so hierarchy filters are applied before completion aggregation.

## API Contract

- Endpoint: GET /backoffice/units
- Query params:
  - years: required list of reporting years
  - path_lvl2: optional list of VP/Faculty filters
  - path_lvl3: optional list of Institute filters
  - path_lvl4: optional list of Unit filters
  - page, page_size, search, completion_status: unchanged
- Response fields consumed by percentage bar:
  - data
  - completion
  - validation_status
  - pagination.total

## Backend Tasks

- Repository/query layer:
  - apply path_lvl2, path_lvl3, and path_lvl4 filters in both:
    - count query used for pagination.total
    - paginated units query used for data rows
  - apply hierarchy filters before completion-status grouping/derivation
  - keep intersection semantics when multiple hierarchy filters are present
- API layer:
  - keep endpoint contract unchanged: GET /backoffice/units
  - keep response schema backward-compatible (no required field additions)
  - preserve current behavior of page, page_size, search, completion_status
- Validation and quality checks:
  - add/update tests for count and data consistency under filters
  - verify unfiltered behavior remains unchanged
  - verify empty-result filters return total = 0 and empty data

## Frontend Tasks

- Reuse existing hierarchy selectors already present in Backoffice reporting:
  - VP/Faculty
  - Institute
  - Unit (optional)
  - Year (required)
- Ensure selected values are mapped to API query params:
  - path_lvl2 from VP/Faculty selector
  - path_lvl3 from Institute selector
  - path_lvl4 from Unit selector
  - years from Year selector
- Call GET /backoffice/units with selected filters.
- Compute values:
  - complete_count: units with completion = validated
  - incomplete_count: total - complete_count
  - complete_percentage: complete_count / total_filtered_units
- Ensure percentage bar and table use the same API response cycle.
- Verify reset/clear behavior keeps table and percentage bar in sync.

## Success Criteria

1. VP/Faculty filtering updates table and percentage bar consistently.
2. Institute filtering narrows both table and percentage bar consistently.
3. Combined VP/Faculty + Institute filtering uses intersection behavior.
4. Percentage values match filtered table totals exactly.
5. No new aggregation endpoint is introduced.
