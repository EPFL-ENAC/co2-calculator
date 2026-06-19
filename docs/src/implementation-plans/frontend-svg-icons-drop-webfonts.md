---
status: in-progress
last_updated: 2026-06-19
title: "Drop Material Icons webfonts in favour of tree-shaken SVG icons"
summary: "Replace the two Quasar Material Icons webfonts (~278 KiB, render-/LCP-blocking, font-display:block FOIT) with in-component SVG imports from @quasar/extras and the svg-material-icons icon set, so only the icons actually used are bundled and no icon webfont is shipped."
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the app with **zero icon webfonts** — every icon rendered as an inline SVG, tree-shaken so only the ~111 icons in use are bundled.

**Architecture:** Two icon surfaces must both move to SVG: (1) **Quasar's internal component icons** (dropdown arrows, sort carets, checkboxes, stepper, pagination, close buttons inside `q-select`/`q-chip`, etc.) — switched in one line via `framework.iconSet: 'svg-material-icons'`; (2) **app-authored icons** — every `<q-icon name="…">`, `icon="…"` prop, and config `icon: '…'` field — converted to in-component named imports from `@quasar/extras/material-icons` (`mat*`) and `@quasar/extras/material-icons-outlined` (`outlined*`). The two webfonts are removed from `extras` only after every call site is converted, so the app renders correctly at every commit. A temporary dev-mode `iconMapFn` guard catches any string icon name that slips through.

**Tech Stack:** Vue 3.5, Quasar 2.19 (`@quasar/app-vite` 2.6), `@quasar/extras` (SVG icon exports), Vite, `vue-tsc` 3.3.5.

## Global Constraints

- **Never remove the fonts before all call sites are converted.** While both fonts remain in `extras`, unconverted string-name icons still render — this is the safety net for incremental conversion. Removing `extras` fonts is the _last_ task.
- **Do not touch `ModuleIcon` / `ModuleIconBox` / `module-icon` plugin usages** (`:name="module"`, `:name="moduleCard.module"`, `:name="row.module"`, …). Those render custom module SVGs (`src/assets/icons/modules/*.svg` via `import.meta.glob` raw import) and are **unaffected** by webfont removal.
- **Do not touch i18n keys, domain strings, or any non-icon `name:`/`icon:` object property.** Many snake_case strings (`room_name`, `results_units_kg`, …) are translation keys, not icons.
- **Backend / API unchanged.** Frontend-only change. PR targets `dev`.
- **Verification gate per task:** `cd frontend && make type-check` (runs `npx vue-tsc --noEmit -p tsconfig.typecheck.json`). There is **no JS unit-test harness** for icons, so the type-checker is the test: a wrong or non-existent export name (e.g. `matInfoOutline`) fails compilation. Plus the per-area grep guard (below). The user runs the full test/e2e suite — stop at type-check + build.
- **Lint:** `cd frontend && npm run lint` must stay green (catches unused imports if a conversion is half-done).

---

## Background — current state (measured 2026-06-18)

Lighthouse on `…/2025/equipment`:

- `flUhRq6tz…woff2` — **126 KiB**, Material Icons, `font-display: block` (FOIT), on LCP critical path (~1,020 ms).
- `gok-H7zzD…woff2` — **152 KiB**, Material Icons Outlined, `font-display: block`, on LCP critical path (~1,249 ms).
- Both injected unconditionally by `quasar.config.js → framework... ` no — by the top-level `extras: ['material-icons', 'material-icons-outlined']`.

Call-site inventory (frontend `src/`):

- `73` `<q-icon name="…">` tags, `88` `icon="…"` literal props, `65` config `icon: '…'` fields, `4` icon literals hidden inside `:name`/`:icon` ternaries (`chevron_left/right`, `lock`, `lock_open`).
- `111` distinct icon names total: **45** base material + **66** outlined.
- **~80 files** across `components/`, `pages/`, `constant/`.
- `:name="…"` bindings that target `ModuleIcon`/`ModuleIconBox` are **out of scope** (custom SVGs).

---

## Conversion recipe (applies to every Task 2–7)

For each affected file:

1. **Template literal → bound SVG import.**
   ```vue
   <!-- before -->
   <!-- after -->
   <q-icon name="close" />
   <q-icon :name="matClose" />
   <q-btn icon="o_info" />
   <q-btn :icon="outlinedInfo" />
   ```
2. **Ternary literal → bound import (import both branches).**
   ```vue
   <!-- before -->
   <q-icon :name="collapsed ? 'chevron_right' : 'chevron_left'" />
   <!-- after -->
   <q-icon :name="collapsed ? matChevronRight : matChevronLeft" />
   ```
3. **Config object field (`.ts` / `<script>`).**
   ```ts
   // before
   { label: 'Close', icon: 'o_close' }
   // after
   import { outlinedClose } from '@quasar/extras/material-icons-outlined'
   { label: 'Close', icon: outlinedClose }
   ```
   The consuming template (`:icon="item.icon"`) stays unchanged — SVG exports are plain `string`s (`"path…|viewBox"`), so existing `icon: string` types still hold.
4. **Add imports at the top of the file**, grouped by source:
   ```ts
   import { matClose, matRefresh } from "@quasar/extras/material-icons";
   import {
     outlinedInfo,
     outlinedClose,
   } from "@quasar/extras/material-icons-outlined";
   ```
5. **Look up the export name in the Mapping Table below.** `o_`-prefixed names → `outlined*` (from `material-icons-outlined`); all others → `mat*` (from `material-icons`).
6. **Do not convert** `ModuleIcon`/`ModuleIconBox`/`module-icon` `:name` bindings, or non-icon properties.

After editing a file, the `name=`/`icon=`/`icon:` literal must be gone (it is now `:name`/`:icon` bound, or `icon: <import>`).

### What NOT to touch (explicit allow-list of survivors)

- `<ModuleIcon :name="…">`, `<ModuleIconBox :name="…">`, `module-icon` — custom module SVGs.
- `:name="icon"` where `icon` is a prop/variable (e.g. `EssentialLink.vue`, `VirtualSelectField.vue`) — already dynamic; the source value gets converted at its origin (config / computed), not here.
- Any `name:`/`icon:` that is not an icon (i18n keys, type discriminators, API fields).

---

## Authoritative Mapping Table

Generated and verified against `@quasar/extras` (every export confirmed to exist). Five names have no exact export — the closest visual match is given and flagged ⚠ for a visual confirm during review.

### material-icons → `@quasar/extras/material-icons` (45)

| name string               | SVG export                  | note                                                |
| ------------------------- | --------------------------- | --------------------------------------------------- |
| `add`                     | `matAdd`                    |                                                     |
| `add_circle`              | `matAddCircle`              |                                                     |
| `adjust`                  | `matAdjust`                 |                                                     |
| `badge`                   | `matBadge`                  |                                                     |
| `bar_chart`               | `matBarChart`               |                                                     |
| `calculate`               | `matCalculate`              |                                                     |
| `calendar_month`          | `matCalendarMonth`          |                                                     |
| `calendar_today`          | `matCalendarToday`          |                                                     |
| `cancel`                  | `matCancel`                 |                                                     |
| `category`                | `matCategory`               |                                                     |
| `check`                   | `matCheck`                  |                                                     |
| `check_box_outline_blank` | `matCheckBoxOutlineBlank`   |                                                     |
| `check_circle`            | `matCheckCircle`            |                                                     |
| `chevron_left`            | `matChevronLeft`            |                                                     |
| `chevron_right`           | `matChevronRight`           |                                                     |
| `circle`                  | `matCircle`                 |                                                     |
| `close`                   | `matClose`                  |                                                     |
| `content_copy`            | `matContentCopy`            |                                                     |
| `data_object`             | `matDataObject`             |                                                     |
| `delete`                  | `matDelete`                 |                                                     |
| `download`                | `matDownload`               |                                                     |
| `edit`                    | `matEdit`                   |                                                     |
| `edit_note`               | `matEditNote`               |                                                     |
| `edit_off`                | `matEditOff`                |                                                     |
| `error`                   | `matError`                  |                                                     |
| `event`                   | `matEvent`                  |                                                     |
| `file_upload`             | `matFileUpload`             |                                                     |
| `grid_view`               | `matGridView`               |                                                     |
| `hourglass_empty`         | `matHourglassEmpty`         |                                                     |
| `lock`                    | `matLock`                   |                                                     |
| `lock_open`               | `matLockOpen`               |                                                     |
| `manufacturing`           | `matPrecisionManufacturing` | ⚠ no exact export — closest match, confirm visually |
| `map`                     | `matMap`                    |                                                     |
| `refresh`                 | `matRefresh`                |                                                     |
| `report`                  | `matReport`                 |                                                     |
| `report_problem`          | `matReportProblem`          |                                                     |
| `restart_alt`             | `matRestartAlt`             |                                                     |
| `search`                  | `matSearch`                 |                                                     |
| `search_off`              | `matSearchOff`              |                                                     |
| `stacked_bar_chart`       | `matStackedBarChart`        |                                                     |
| `sync`                    | `matSync`                   |                                                     |
| `unfold_more`             | `matUnfoldMore`             |                                                     |
| `upload`                  | `matUpload`                 |                                                     |
| `view_module`             | `matViewModule`             |                                                     |
| `warning`                 | `matWarning`                |                                                     |

### material-icons-outlined → `@quasar/extras/material-icons-outlined` (66)

| name string               | SVG export                    | note                                                |
| ------------------------- | ----------------------------- | --------------------------------------------------- |
| `info_outline`            | `outlinedInfo`                | ⚠ no exact export — closest match, confirm visually |
| `o_ac_unit`               | `outlinedAcUnit`              |                                                     |
| `o_account_tree`          | `outlinedAccountTree`         |                                                     |
| `o_add_box`               | `outlinedAddBox`              |                                                     |
| `o_add_circle`            | `outlinedAddCircle`           |                                                     |
| `o_add_comment`           | `outlinedAddComment`          |                                                     |
| `o_air`                   | `outlinedAir`                 |                                                     |
| `o_apartment`             | `outlinedApartment`           |                                                     |
| `o_apps`                  | `outlinedApps`                |                                                     |
| `o_article`               | `outlinedArticle`             |                                                     |
| `o_assessment`            | `outlinedAssessment`          |                                                     |
| `o_assignment`            | `outlinedAssignment`          |                                                     |
| `o_assignment_ind`        | `outlinedAssignmentInd`       |                                                     |
| `o_autorenew`             | `outlinedAutorenew`           |                                                     |
| `o_bar_chart`             | `outlinedBarChart`            |                                                     |
| `o_bolt`                  | `outlinedBolt`                |                                                     |
| `o_business`              | `outlinedBusiness`            |                                                     |
| `o_calculate`             | `outlinedCalculate`           |                                                     |
| `o_calendar_month`        | `outlinedCalendarMonth`       |                                                     |
| `o_category`              | `outlinedCategory`            |                                                     |
| `o_check_circle`          | `outlinedCheckCircle`         |                                                     |
| `o_check_small`           | `outlinedCheck`               | ⚠ no exact export — closest match, confirm visually |
| `o_close`                 | `outlinedClose`               |                                                     |
| `o_content_copy`          | `outlinedContentCopy`         |                                                     |
| `o_delete`                | `outlinedDelete`              |                                                     |
| `o_diversity_2`           | `outlinedDiversity2`          |                                                     |
| `o_donut_large`           | `outlinedDonutLarge`          |                                                     |
| `o_download`              | `outlinedDownload`            |                                                     |
| `o_edit`                  | `outlinedEdit`                |                                                     |
| `o_edit_document`         | `outlinedEditNote`            | ⚠ no exact export — closest match, confirm visually |
| `o_electric_bolt`         | `outlinedElectricBolt`        |                                                     |
| `o_error`                 | `outlinedError`               |                                                     |
| `o_event`                 | `outlinedEvent`               |                                                     |
| `o_filter_drama`          | `outlinedFilterDrama`         |                                                     |
| `o_flight`                | `outlinedFlight`              |                                                     |
| `o_help_center`           | `outlinedHelpCenter`          |                                                     |
| `o_image_aspect_ratio`    | `outlinedImageAspectRatio`    |                                                     |
| `o_info`                  | `outlinedInfo`                |                                                     |
| `o_light_mode`            | `outlinedLightMode`           |                                                     |
| `o_list_alt`              | `outlinedListAlt`             |                                                     |
| `o_local_fire_department` | `outlinedLocalFireDepartment` |                                                     |
| `o_lock`                  | `outlinedLock`                |                                                     |
| `o_mail`                  | `outlinedMail`                |                                                     |
| `o_meeting_room`          | `outlinedMeetingRoom`         |                                                     |
| `o_notifications`         | `outlinedNotifications`       |                                                     |
| `o_pending`               | `outlinedPending`             |                                                     |
| `o_people`                | `outlinedPeople`              |                                                     |
| `o_picture_as_pdf`        | `outlinedPictureAsPdf`        |                                                     |
| `o_pie_chart`             | `outlinedPieChart`            |                                                     |
| `o_print`                 | `outlinedPrint`               |                                                     |
| `o_report_problem`        | `outlinedReportProblem`       |                                                     |
| `o_save`                  | `outlinedSave`                |                                                     |
| `o_schema`                | `outlinedSchema`              |                                                     |
| `o_science`               | `outlinedScience`             |                                                     |
| `o_search`                | `outlinedSearch`              |                                                     |
| `o_search_off`            | `outlinedSearchOff`           |                                                     |
| `o_sell`                  | `outlinedSell`                |                                                     |
| `o_straighten`            | `outlinedStraighten`          |                                                     |
| `o_swap_horiz`            | `outlinedSwapHoriz`           |                                                     |
| `o_table`                 | `outlinedTableChart`          | ⚠ no exact export — closest match, confirm visually |
| `o_thermostat`            | `outlinedThermostat`          |                                                     |
| `o_timer`                 | `outlinedTimer`               |                                                     |
| `o_view_cozy`             | `outlinedViewCozy`            |                                                     |
| `o_view_list`             | `outlinedViewList`            |                                                     |
| `o_visibility`            | `outlinedVisibility`          |                                                     |
| `o_warning`               | `outlinedWarning`             |                                                     |

> If a name appears in code that is **not** in this table, do not guess: derive the export with the rule (`o_x_y → outlinedXY`, else `matXY`), confirm it exists with
> `node -e "console.log('matFoo' in require('@quasar/extras/material-icons'))"`, add a table row, and only then convert.

---

## Per-area grep guard

Run after each Task 2–7 against that task's files (and globally before Task 8). It must print **nothing** for converted files:

```bash
cd frontend
# remaining literal icon names (excludes ModuleIcon's :name bindings, which have no quotes)
grep -rnE "<q-icon[^>]*\bname=\"[a-z]|\bicon=\"[a-z][a-z_0-9]+\"|\bicon:[[:space:]]*['\"][a-z][a-z_0-9]+['\"]|['\"]o_[a-z]" <FILES>
# literal icon names hidden in bound expressions
grep -rnE ":(icon|name)=\"[^\"]*'(lock|lock_open|chevron_left|chevron_right)'" <FILES>
```

---

### Task 1: Switch Quasar internal icons to the SVG icon set

**Files:**

- Modify: `frontend/quasar.config.js` (the `framework: { … }` block, ~line 214)

**Interfaces:**

- Produces: Quasar's built-in component icons now resolve from `quasar/icon-set/svg-material-icons` (inline SVG) instead of the Material Icons font. The `extras` fonts remain, so app string-name icons are unaffected.

- [ ] **Step 1: Add the SVG icon set to the framework config**

```js
    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#framework
    framework: {
      iconSet: 'svg-material-icons',
      plugins: [
        'Dialog',
        'Loading',
        'Notify',
        'LocalStorage',
        'SessionStorage',
        'Meta',
      ],
      cssAddon: false,
    },
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && make type-check`
Expected: PASS (config change only; no TS impact).

- [ ] **Step 3: Build + visual smoke**

Run: `cd frontend && npm run build`
Expected: build succeeds. Serve the build (or `quasar dev`) and confirm Quasar **internal** icons render as SVG: `q-select` dropdown arrow, `q-table` sort caret, `q-checkbox`/`q-radio`, `q-expansion-item` chevron, `q-pagination` arrows, the `×` in `q-chip`/closable notifications. (App-authored icons still use the font here — that's expected.)

- [ ] **Step 4: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add frontend/quasar.config.js
git commit -m "feat(frontend): use svg-material-icons icon set for Quasar internals"
```

---

### Task 2: Convert `constant/` config files

**Files (11):**

- Modify: `frontend/src/constant/module-config/buildings.ts`, `equipment.ts`, `headcount.ts`, `process_emissions.ts`, `external-cloud-and-ai.ts`, `purchase.ts`
- Modify: `frontend/src/constant/navigation.ts`, `timelineItems.ts`, `report.ts`, `moduleStates.ts`, `backoffice-module-config.ts`

**Interfaces:**

- Consumes: the Mapping Table.
- Produces: every `icon:` field in these modules holds an imported SVG export (a `string`), so all `:icon="cfg.icon"` / `:name="item.icon"` template bindings downstream render SVG. Field types stay `string` — no interface changes.

- [ ] **Step 1: Convert each file per the recipe** — replace every `icon: '<name>'` with `icon: <export>`, add the grouped imports at the top. Use the Mapping Table for export names. `navigation.ts` uses `o_edit_document` (×2) → `outlinedEditNote` (⚠ confirm visually).

- [ ] **Step 2: Type-check**

Run: `cd frontend && make type-check`
Expected: PASS. A typo'd or non-existent export fails here.

- [ ] **Step 3: Lint (catch unused/forgotten imports)**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 4: Grep guard**

Run the per-area grep guard with `<FILES>` = the 11 files above.
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/constant
git commit -m "feat(frontend): convert constant/ icon config to SVG imports"
```

---

### Task 3: Convert `components/molecules`, `components/atoms`, `components/layout`, `components/charts`, `components/EssentialLink.vue`

**Files (~26):** all `.vue` under `frontend/src/components/molecules/` (14), `frontend/src/components/atoms/` (1), `frontend/src/components/layout/` (3), `frontend/src/components/charts/` (7), and `frontend/src/components/EssentialLink.vue` that contain an icon literal per the guard.

**Interfaces:**

- Consumes: the Mapping Table. Note `charts/EmissionBreakdownChart.vue` uses `info_outline` → `outlinedInfo` (⚠).
- Produces: all icon literals in these files converted to bound SVG imports.

- [ ] **Step 1: Find the exact files**

Run:

```bash
cd frontend && grep -rlE "(\bicon=\"[a-z]|<q-icon[^>]*name=\"[a-z]|['\"]o_[a-z]|\bicon:[[:space:]]*['\"][a-z]|:(icon|name)=\"[^\"]*'(lock|lock_open|chevron_left|chevron_right)')" \
  src/components/molecules src/components/atoms src/components/layout src/components/charts src/components/EssentialLink.vue
```

- [ ] **Step 2: Convert each file per the recipe.** Leave `EssentialLink.vue`'s `:name="icon"` (bound prop) alone — only convert any literal there, if present.

- [ ] **Step 3: Type-check** — `cd frontend && make type-check` → PASS.
- [ ] **Step 4: Lint** — `cd frontend && npm run lint` → PASS.
- [ ] **Step 5: Grep guard** over the Step-1 file list → no output.
- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/molecules frontend/src/components/atoms frontend/src/components/layout frontend/src/components/charts frontend/src/components/EssentialLink.vue
git commit -m "feat(frontend): convert molecule/atom/layout/chart icons to SVG imports"
```

---

### Task 4: Convert `components/organisms`

**Files (~20):** all `.vue` under `frontend/src/components/organisms/` matching the guard (module, backoffice/reporting, data-management subtrees). `ModuleCharts.vue` uses `info_outline` → `outlinedInfo` (⚠); `backoffice/reporting/ReportExport.vue` uses `o_table` → `outlinedTableChart` (⚠); `backoffice/reporting/ReportingFilters.vue` uses `o_check_small` → `outlinedCheck` (⚠).

**Interfaces:** Consumes the Mapping Table.

- [ ] **Step 1: List files** — `cd frontend && grep -rlE "(\bicon=\"[a-z]|<q-icon[^>]*name=\"[a-z]|['\"]o_[a-z]|\bicon:[[:space:]]*['\"][a-z])" src/components/organisms`
- [ ] **Step 2: Convert per recipe.** Do **not** touch `ModuleIcon`/`ModuleIconBox`/`module-icon` `:name` bindings.
- [ ] **Step 3: Type-check** → PASS.
- [ ] **Step 4: Lint** → PASS.
- [ ] **Step 5: Grep guard** over those files → no output.
- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/organisms
git commit -m "feat(frontend): convert organism icons to SVG imports"
```

---

### Task 5: Convert `components/audit`

**Files (~6):** all `.vue` under `frontend/src/components/audit/` matching the guard. `AuditFilterBar.vue` uses `manufacturing` → `matPrecisionManufacturing` (⚠).

**Interfaces:** Consumes the Mapping Table.

- [ ] **Step 1: List files** — `cd frontend && grep -rlE "(\bicon=\"[a-z]|<q-icon[^>]*name=\"[a-z]|['\"]o_[a-z]|\bicon:[[:space:]]*['\"][a-z])" src/components/audit`
- [ ] **Step 2: Convert per recipe.**
- [ ] **Step 3: Type-check** → PASS.
- [ ] **Step 4: Lint** → PASS.
- [ ] **Step 5: Grep guard** → no output.
- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/audit
git commit -m "feat(frontend): convert audit icons to SVG imports"
```

---

### Task 6: Convert `pages/`

**Files (~16):** all `.vue` under `frontend/src/pages/app/` (7), `frontend/src/pages/back-office/` (7), plus `frontend/src/pages/ErrorUnauthorized.vue`, `frontend/src/pages/ErrorNotFound.vue` matching the guard. `back-office/PipelineOperationsConsolePage.vue` holds `icon:` config literals; `ResultsPage.vue`/`HomePage.vue` use `ModuleIconBox`/`module-icon` `:name="module"` bindings which must be **left untouched**.

**Interfaces:** Consumes the Mapping Table.

- [ ] **Step 1: List files** — `cd frontend && grep -rlE "(\bicon=\"[a-z]|<q-icon[^>]*name=\"[a-z]|['\"]o_[a-z]|\bicon:[[:space:]]*['\"][a-z]|:(icon|name)=\"[^\"]*'(lock|lock_open|chevron_left|chevron_right)')" src/pages`
- [ ] **Step 2: Convert per recipe.** Includes ternary literals (`:icon="… ? 'lock_open' : 'lock'"` → `matLockOpen`/`matLock`).
- [ ] **Step 3: Type-check** → PASS.
- [ ] **Step 4: Lint** → PASS.
- [ ] **Step 5: Grep guard** → no output.
- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages
git commit -m "feat(frontend): convert page icons to SVG imports"
```

---

### Task 7: Convert remaining `.ts` icon strings (Notify/Dialog/util call sites)

**Files (3):**

- Modify: `frontend/src/utils/errors.ts`, `frontend/src/api/http.ts`, `frontend/src/boot/sentry.ts`

These hold `icon: '<name>'` passed to `Notify.create` / `Dialog.create` / error helpers.

**Interfaces:** Consumes the Mapping Table.

- [ ] **Step 1: Convert each `icon: '<name>'` to `icon: <export>` with a top-of-file import.**
- [ ] **Step 2: Type-check** → PASS.
- [ ] **Step 3: Lint** → PASS.
- [ ] **Step 4: Grep guard** over the 3 files → no output.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/errors.ts frontend/src/api/http.ts frontend/src/boot/sentry.ts
git commit -m "feat(frontend): convert Notify/Dialog icon strings to SVG imports"
```

---

### Task 8: Drop both webfonts + add dev-mode guard

**Files:**

- Create: `frontend/src/boot/icon-guard.ts`
- Modify: `frontend/quasar.config.js` (remove fonts from `extras`; register the new boot file)

**Interfaces:**

- Consumes: all of Tasks 1–7 complete (no string icon literals remain anywhere).
- Produces: no icon webfont shipped; a dev-only `iconMapFn` that surfaces any string icon name still reaching a Quasar component.

- [ ] **Step 1: Global grep guard (whole `src/`) must be clean**

Run:

```bash
cd frontend
grep -rnE "<q-icon[^>]*\bname=\"[a-z]|\bicon=\"[a-z][a-z_0-9]+\"|\bicon:[[:space:]]*['\"][a-z][a-z_0-9]+['\"]|['\"]o_[a-z]" src --include='*.vue' --include='*.ts'
grep -rnE ":(icon|name)=\"[^\"]*'(lock|lock_open|chevron_left|chevron_right)'" src --include='*.vue'
```

Expected: **no output**. If anything prints, convert it (Tasks 2–7 recipe) before continuing.

- [ ] **Step 2: Add the dev-mode guard boot file**

Create `frontend/src/boot/icon-guard.ts`:

```ts
import { boot } from "quasar/wrappers";

// Dev-only safety net for the SVG-icon migration: any *string* icon name that
// still reaches a Quasar component (q-icon, q-btn icon, Notify, ...) means a
// call site was missed and would render blank now that the webfonts are gone.
// SVG icons arrive as a path string starting with "M"/"m" or an "img:" / "svguse:"
// reference, so a bare word like "close" is the tell.
export default boot(({ app }) => {
  if (!import.meta.env.DEV) return;
  const looksLikeName = (s: string) =>
    /^[a-z][a-z0-9_]*$/.test(s) &&
    !s.startsWith("img:") &&
    !s.startsWith("svguse:");
  app.config.globalProperties.$q.iconMapFn = (iconName: string) => {
    if (typeof iconName === "string" && looksLikeName(iconName)) {
      // eslint-disable-next-line no-console
      console.error(
        `[icon-guard] unconverted string icon name reached a component: "${iconName}"`,
      );
    }
    return undefined; // let Quasar handle it normally
  };
});
```

> Quasar's `iconMapFn` runs for every icon resolution; returning `undefined` is a no-op pass-through. This stays in the codebase (dev-only, tree-shaken out of prod by the `import.meta.env.DEV` guard) as a regression net.

- [ ] **Step 3: Register the boot file and remove the fonts**

In `frontend/quasar.config.js`:

```js
    // boot files
    boot: ['sentry', 'i18n', 'router', 'icons', 'icon-guard'],

    // extras — icon webfonts removed; icons now ship as tree-shaken SVG
    extras: [],
```

(If `extras: []` ends up empty and Quasar/lint complains, leave the key as `extras: []` — it is valid. Keep any non-icon entries if present; there are none today.)

- [ ] **Step 4: Type-check + lint**

Run: `cd frontend && make type-check && npm run lint`
Expected: PASS.

- [ ] **Step 5: Build and verify no icon webfont is emitted**

Run:

```bash
cd frontend && npm run build
# no Material Icons woff2 in the build output:
find dist -name '*.woff2' | xargs -I{} basename {}
```

Expected: build succeeds; the listed `.woff2` are **only** the SuisseIntl text fonts (`SuisseIntlEPFL-*`). No `flUhRq6tz…` / `gok-H7zzD…` (Material Icons) woff2.

- [ ] **Step 6: Runtime visual sweep (dev)**

Run `cd frontend && quasar dev`, open the console, and click through the highest-icon-density pages: the equipment/results module page, a module form, backoffice reporting (filters, export, stat cards), audit filter bar, navigation drawer, error pages. Confirm:

- No blank/missing icons.
- **Zero** `[icon-guard]` console errors.
- The five ⚠ substitutions look right: `outlinedInfo` (info_outline), `matPrecisionManufacturing` (manufacturing), `outlinedCheck` (o_check_small), `outlinedEditNote` (o_edit_document), `outlinedTableChart` (o_table).

- [ ] **Step 7: Update this plan's status to `delivered` and commit**

```bash
# set frontmatter status: delivered, last_updated: <today>
git add frontend/quasar.config.js frontend/src/boot/icon-guard.ts docs/src/implementation-plans/frontend-svg-icons-drop-webfonts.md
git commit -m "feat(frontend): drop Material Icons webfonts, ship SVG icons only"
```

---

## Self-Review

**Spec coverage:**

- "Genuinely use in-component SVG imports for tree-shaking" → Tasks 2–7 convert every app call site to named `@quasar/extras` imports; Vite bundles only referenced exports. ✓
- "Drop both fonts, only SVG icons" → Task 1 (internals via `svg-material-icons`) + Task 8 (`extras: []`, build asserts no Material Icons woff2). ✓
- Quasar internal icons (not call sites) → Task 1. ✓
- Hidden ternary/computed literals → covered by recipe step 2, the per-area guards, and the Task 8 runtime `iconMapFn` guard. ✓
- Module/custom SVG icons untouched → stated in Global Constraints + every task. ✓

**Placeholder scan:** Mapping Table fully enumerated (111 rows, all exports verified to exist); five no-exact-export names resolved to a named closest match and flagged. No "TBD"/"handle edge cases". ✓

**Type consistency:** Export-name convention (`o_x → outlinedX`, else `matX`) is applied uniformly; config `icon:` fields stay typed `string` (SVG exports are strings), so no interface drift. Guard `iconMapFn` signature matches Quasar's `(name: string) => IconMapEntry | void`. ✓

**Ordering safety:** Fonts removed only in Task 8, after every site is converted and the global guard is clean; the app renders at every intermediate commit. ✓

## Notes / follow-ups (out of scope here)

- After merge, re-run Lighthouse on `…/2025/equipment` to confirm the 278 KiB icon-font payload and its FOIT are gone from the LCP critical path.
- The `index.html` SuisseIntl preloads + `injectEnv.js defer` (shipped separately) remain valid and unrelated.
