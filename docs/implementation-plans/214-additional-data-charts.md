# Issue #214 — Additional Data in Results Page (Food, Commuting, Waste, Grey Energy)

## Context

The Results page currently shows carbon footprint data for validated modules (Equipment, Professional Travel, Buildings, etc.) via:

1. **Summary BigNumber cards** — total CO2, per-FTE, year-over-year comparison
2. **Two big charts** — `ModuleCarbonFootprintChart` (stacked bar) and `CarbonFootPrintPerPersonChart`
3. **Results by Category** — expandable sections per module with treemaps and BigNumber cards

The big charts already support a **"Show additional estimated categories"** toggle that displays food, commuting, waste, and grey energy bars (headcount-derived, FTE-based estimates). However, there is **no dedicated sub-section** in the results page that shows these additional categories with their own numbers and details — they only appear as extra bars in the charts.

### What this issue asks for

1. A new **collapsible sub-section** (similar to "Results by Category") that shows the additional estimated categories (food, commuting, waste, grey energy) with their own BigNumber stat cards
2. The sub-section and chart bars should **only appear** when a checkbox "Show additional categories" is checked (default: checked)
3. The checkbox should be placed next to the existing "Colorblind mode" / "View Uncertainties" controls at the top of the results page
4. These results should **only appear when the Headcount module is validated**
5. Grey energy is tracked separately in issue #701 — may need special handling

### Sub-issue #836

A sub-issue "[FEAT] [Result] Sub-section Additional Categories" (#836) tracks the actual sub-section implementation.

---

## Current State Analysis

### What already exists

| Component                                                                                  | Status             |
| ------------------------------------------------------------------------------------------ | ------------------ |
| Backend `additional_breakdown` in emission-breakdown endpoint                              | Done               |
| Backend `HEADCOUNT_PER_FTE_KG` constants (food=420, waste=125, commuting=1375 kg/FTE/year) | Done               |
| Chart toggle checkbox "Show additional estimated categories"                               | Done               |
| Chart series for commuting, food, waste, grey_energy                                       | Done               |
| i18n strings for toggle label                                                              | Done               |
| Colorblind-safe colors for additional categories                                           | Done               |
| Results page sub-section for additional categories                                         | **Not done**       |
| Top-level checkbox controlling both charts AND sub-section                                 | **Not done**       |
| BigNumber cards for each additional category                                               | **Not done**       |
| Grey energy data/factors (#701)                                                            | **Not done / TBD** |

### Key files

| Area                         | File                                                                       |
| ---------------------------- | -------------------------------------------------------------------------- |
| Results page                 | `frontend/src/pages/app/ResultsPage.vue`                                   |
| Big chart (module breakdown) | `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`    |
| Per-person chart             | `frontend/src/components/charts/results/CarbonFootPrintPerPersonChart.vue` |
| BigNumber card component     | `frontend/src/components/molecules/BigNumber.vue`                          |
| Module store (data fetching) | `frontend/src/stores/modules.ts`                                           |
| Backend breakdown logic      | `backend/app/utils/emission_category.py`                                   |
| Backend stats API            | `backend/app/api/v1/carbon_report_module_stats.py`                         |
| i18n translations            | `frontend/src/i18n/results.ts`                                             |
| Chart colors                 | `frontend/src/constant/charts.ts`                                          |

---

## Implementation Plan

### Step 1: Lift toggle state to ResultsPage level

**Goal**: Move the "Show additional categories" toggle from inside each chart to a page-level control on the **Results page only**, so it governs both charts AND the new sub-section. The backoffice `ReportingPage.vue` keeps its existing per-chart toggles unchanged.

**Changes**:

1. **`ResultsPage.vue`** — Add a `showAdditionalCategories` ref (default: `true`, only enabled when headcount is validated). Add a checkbox next to the existing "Colorblind mode" and "View Uncertainties" checkboxes in the header controls area (lines 155-180).

2. **`ModuleCarbonFootprintChart.vue`** — Add an optional prop `showAdditionalData?: boolean`. When the prop is provided, use it and hide the internal checkbox. When the prop is `undefined` (i.e. used from `ReportingPage.vue`), keep the existing internal `toggleAdditionalData` ref and internal checkbox as-is.

3. **`CarbonFootPrintPerPersonChart.vue`** — Same approach: optional prop, fallback to internal toggle when not provided.

4. **`ResultsPage.vue`** — Pass `showAdditionalCategories` as a prop to both chart components.

**Why**: The issue spec says the checkbox should be at the page level and control both charts + the sub-section on the Results page. The backoffice reporting page (`ReportingPage.vue`) already has its own per-chart toggles which must remain unchanged.

**Important**: The backoffice `ReportingPage.vue` uses the same chart components but should NOT be affected by this change. The optional prop pattern ensures backward compatibility.

---

### Step 2: Add "Additional Categories" sub-section to Results page

**Goal**: Below the "Results by Category" section (or as part of it), add a new collapsible section that shows BigNumber cards for each additional category.

**Changes**:

1. **`ResultsPage.vue`** — After the existing `MODULES_LIST` loop (line ~497), add a new section wrapped in `v-if="showAdditionalCategories && headcountValidated"`:

   ```vue
   <q-card
     bordered
     flat
     class="q-pa-xl q-mt-xl"
     v-if="showAdditionalCategories && headcountValidated"
   >
     <h2>{{ $t('results_additional_categories_title') }}</h2>
     <span>{{ $t('results_additional_categories_subtitle') }}</span>
   
     <template v-for="category in additionalCategories" :key="category.key">
       <q-expansion-item>
         <!-- Category header with icon -->
         <!-- BigNumber cards: total, per-FTE, year comparison -->
       </q-expansion-item>
     </template>
   </q-card>
   ```

2. **Data source**: Use `emissionBreakdown.additional_breakdown` from the store. Each entry in `additional_breakdown` already contains `{ category, label, values: [{ value, std_dev }], validated }`. Wire these into `BigNumber` cards with the same layout as the module sections (total, per-FTE, year comparison).

3. **Computed property** `additionalCategories`: Map `additional_breakdown` entries to a display-ready format with:
   - Category name (from i18n: `charts-food-category`, `charts-waste-category`, `charts-commuting-category`, `charts-grey-energy-category`)
   - Total tonnes CO2eq
   - Per-FTE value
   - Year-over-year comparison (if previous year data available)
   - Car km equivalence

---

### Step 3: Update BigNumber summary cards

**Goal**: When "Show additional categories" is checked, the top-level summary BigNumber cards (total carbon footprint, per-FTE) should include the additional categories in their totals.

**Changes**:

1. **`ResultsPage.vue`** — The top BigNumber cards currently show `emissionBreakdown.total_tonnes_co2eq`. When `showAdditionalCategories` is true, add the additional breakdown totals to this value.

2. Create a computed `displayTotalTonnesCo2eq` that sums base + additional when toggle is on.

3. Similarly adjust the per-FTE BigNumber card.

**Note**: Check whether the backend already includes additional categories in `total_tonnes_co2eq` or not. If it does, the logic should subtract when toggle is off rather than add when on.

---

### Step 4: Add i18n strings

**File**: `frontend/src/i18n/results.ts`

Add translations for:

- `results_additional_categories_title` — "Additional estimated categories" / "Catégories supplémentaires estimées"
- `results_additional_categories_subtitle` — Explanatory text about FTE-based estimates
- `results_show_additional_categories` — Checkbox label (can reuse existing `results_module_carbon_toggle_additional_data`)
- Per-category titles for BigNumber cards (may already exist as `charts-*-category` keys)

---

### Step 5: Handle grey energy (#701)

**Goal**: Grey energy is a separate initiative. The implementation should accommodate it but not block on it.

**Changes**:

1. Include `grey_energy` / `embodied_energy` in the additional categories list but mark it as "coming soon" or hide it if no data exists.
2. The backend `EmissionCategory.embodied_energy` enum value already exists. The `ADDITIONAL_BREAKDOWN_ORDER` already includes it.
3. If no per-FTE factor exists for grey energy yet, the backend will return 0 — the frontend should hide categories with no data rather than showing empty cards.

---

### Step 6: Ensure correct conditional display

**Goal**: Additional categories section and chart bars only show when conditions are met.

**Conditions**:

- Headcount module must be validated (`headcount_validated === true` from breakdown response)
- Total FTE must be > 0 (`total_fte > 0`)
- User must have "Show additional categories" checked

**Changes**:

1. **Checkbox disabled state**: Disable (grey out) the "Show additional categories" checkbox when headcount is not validated. Show a tooltip explaining why.
2. **Sub-section visibility**: `v-if="showAdditionalCategories && headcountValidated && totalFte > 0"`
3. **Chart props**: Already handled — charts receive the boolean prop and conditionally render additional series.

---

### Step 7: Colorblind mode support

**Already done** — The chart colors in `frontend/src/constant/charts.ts` already define colorblind variants for all additional category colors. The sub-section icons/badges should use the same color constants for consistency.

---

## Summary of changes by file

| File                                | Changes                                                                                                                                           |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ResultsPage.vue`                   | Add page-level toggle, pass as prop to charts, add additional categories sub-section with BigNumber cards, adjust summary totals                  |
| `ModuleCarbonFootprintChart.vue`    | Add optional `showAdditionalData` prop; when provided, use it and hide internal checkbox; when absent (backoffice), keep existing internal toggle |
| `CarbonFootPrintPerPersonChart.vue` | Same as above — optional prop with fallback to internal toggle for backoffice compatibility                                                       |
| `frontend/src/i18n/results.ts`      | Add i18n strings for sub-section title, subtitle                                                                                                  |
| Backend                             | No changes needed — `additional_breakdown` endpoint already provides all required data                                                            |

## Open questions

1. **Grey energy factors**: Are per-FTE kg values defined for grey energy yet? If not, should we show a placeholder or hide entirely?
2. **Year comparison for additional categories**: The backend returns breakdown per year. Does it return previous year additional breakdown data for comparison? Need to verify.
3. **PDF export**: The results page has a "Download PDF" button. Should the additional categories sub-section be included in the PDF? If so, the PDF generation logic needs updating.
4. **Sub-section placement**: Should the additional categories sub-section appear before or after "Results by Category"? The issue says "a new sub-section (collapsible)" — confirm with design.
5. **Default checkbox state**: Issue says "Check by default" — confirm this is still desired, as it changes the default total shown to users.
