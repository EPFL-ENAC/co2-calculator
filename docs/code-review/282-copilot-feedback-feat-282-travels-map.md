# Bot Review TODOs: PR #1481

Source Branch: `feat/282-travels-map`
---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR adds an interactive “Trips map” for the **Professional Travel** module, including multi-mode rendering (plane/train), richer hover tooltips (including travelers), and a manager-only member filter that can spotlight/dim routes. Backend trip-leg payloads are extended to carry `traveler_id` / `traveler_name`, with traveler names resolved from the headcount roster (fallback to `User.display_name` then institutional id).

**Changes:**

- Frontend: split trips-map aggregation/filter logic into a pure helper module and extend the map UI with mode toggles, member filtering/hover spotlighting, and an expanded hover popup.
- Backend: include traveler attribution on trip legs and resolve traveler display names via headcount roster + user fallback; update unit/integration tests accordingly.
- UI layout: relocate the Professional Travel trips map rendering to `ModuleCharts.vue` and adjust download button placement to avoid duplication.

### Key Review Findings (blocking)

- **Bug (frontend): direction-normalisation key can be wrong due to lexicographic coordinate comparison.**  
  In `frontend/src/utils/trips-map-data.ts` (`routeKeyFor`, around lines 30–36), the code compares stringified coordinates like `"10,0" < "2,0"`, which can produce incorrect key ordering and break aggregation/highlighting for some routes.  
  **Fix:** compare numeric `(lng, lat)` tuples (e.g., `destLng < originLng || (== && destLat < originLat)`).

- **Bug (frontend): basemap recolor uses `fill-color` even for `fill-extrusion` layers.**  
  In `frontend/src/components/molecules/TripsMap.vue` (`recolorSeas`, around lines 446–451), the code sets `fill-color` / `fill-opacity` for both `fill` and `fill-extrusion`. MapLibre uses `fill-extrusion-color` / `fill-extrusion-opacity` for extrusion layers; setting the wrong paint property can no-op or error depending on layer presence.  
  **Fix:** branch on `layer.type` and set the correct paint property names.

- **Bug / API behavior (backend): catching all `HTTPException` can mask real failures.**  
  In `backend/app/api/v1/carbon_report_module.py` (around lines 592–601), the code swallows _any_ `HTTPException` when looking up the headcount module id. This risks hiding non-404 errors (e.g., auth/permission/validation) and silently degrading behavior.  
  **Fix:** only treat 404 as “no headcount module”; re-raise other HTTP errors.

### Reviewed changes

Copilot reviewed 15 out of 15 changed files in this pull request and generated no comments.

<details>
<summary>Show a summary per file</summary>

| File                                                               | Description                                                                                             |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| frontend/tests/unit/trips-map.spec.ts                              | Adds unit tests for traveler aggregation and member-filter helper behavior.                             |
| frontend/src/utils/trips-map.ts                                    | Re-exports pure helpers; updates ramp/colors and adds popup HTML builder + GeoJSON dimming support.     |
| frontend/src/utils/trips-map-data.ts                               | New pure aggregation + member-filter helper module (selection, hover highlighting, totals).             |
| frontend/src/stores/modules.ts                                     | Extends `TripLeg` with `traveler_id` / `traveler_name`.                                                 |
| frontend/src/i18n/professional_travel.ts                           | Adds i18n strings for popup rows and member/mode filter UI.                                             |
| frontend/src/components/organisms/module/SubModuleSection.vue      | Removes per-submodule trips-map rendering (map now centralized elsewhere).                              |
| frontend/src/components/organisms/module/ModuleCharts.vue          | Adds Professional Travel-specific layout for PNG download + trips map placement.                        |
| frontend/src/components/molecules/TripsMap.vue                     | Implements mode multi-select, member filter + hover spotlighting, new vector basemap, and richer popup. |
| backend/tests/unit/services/test_data_entry_service.py             | Tests traveler name resolution via headcount roster fallback behavior.                                  |
| backend/tests/unit/repositories/test_data_entry_repo_trips_map.py  | Tests repo leg payload carries traveler fields and resolves display name fallback logic.                |
| backend/tests/integration/v1/test_professional_travel_trips_map.py | Updates API expectations to include traveler fields and wires new service arg.                          |
| backend/app/services/data_entry_service.py                         | Adds headcount-module-based traveler name resolution step.                                              |
| backend/app/schemas/carbon_report_response.py                      | Adds `traveler_id` / `traveler_name` to `TripLeg` schema with defaults.                                 |
| backend/app/repositories/data_entry_repo.py                        | Left-joins `User` to resolve `traveler_name` and returns traveler fields in legs.                       |
| backend/app/api/v1/carbon_report_module.py                         | Looks up headcount module id and passes it into trips-map service call.                                 |

</details>

---

## Action Items

### Critical: logic, security, correctness

- [x] **backend/app/api/v1/carbon_report_module.py** (~592–601) — the headcount-module lookup wrapped `get_carbon_report_id` in a blanket `except HTTPException`, which would swallow any HTTP error, not just the intended "no headcount module" 404. **Fixed**: re-raise when `exc.status_code != status.HTTP_404_NOT_FOUND`, else fall back to `None`.

### Maintainability / refactoring

- [x] **frontend/src/components/molecules/TripsMap.vue** (`recolorSeas`, ~446–451) — applied `fill-color`/`fill-opacity` to `fill-extrusion` layers too, but extrusion layers use `fill-extrusion-color`/`fill-extrusion-opacity`. **Fixed**: only recolour `fill` layers (seas are never extruded in this basemap), dropping `fill-extrusion` from the check.

### Dropped after verification

- **frontend/src/utils/trips-map-data.ts** (`routeKeyFor`, ~30–36) — Copilot flagged the lexicographic coordinate comparison (`"10,0" < "2,0"`) as breaking aggregation/highlighting. **Wrong**: string comparison is still a deterministic total order, so A→B and B→A always normalise to the same canonical key, and `aggregateLegs` + `travelerRouteKeys` feed `routeKeyFor` the same (origin, dest) argument order, so their keys always match. The only effect is which endpoint becomes "from" vs "to" — purely cosmetic (plane-arc bow direction). No fix needed; could switch to numeric tuples for readability, but not a correctness issue.
