---
status: delivered
last_updated: 2026-09-10
title: "Drop Material Icons webfonts in favour of tree-shaken SVG icons"
summary: "Replace the two Quasar Material Icons webfonts (~278 KiB of woff2, render-/LCP-blocking, font-display:block FOIT) with in-component SVG imports from @quasar/extras and the svg-material-icons icon set, so only the icons actually used are bundled and no icon webfont is shipped."
---

**Goal:** Ship the app with **zero icon webfonts** — every icon rendered as an inline SVG, tree-shaken so only the icons in use are bundled.

**Architecture:** Two icon surfaces both moved to SVG: (1) **Quasar's internal component icons** (dropdown arrows, sort carets, checkboxes, stepper, pagination, close buttons inside `q-select`/`q-chip`) — switched in one line via `framework.iconSet: 'svg-material-icons'`; (2) **app-authored icons** — every `<q-icon name="…">`, `icon="…"` prop, and config `icon: '…'` field — converted to in-component named imports from `@quasar/extras/material-icons` (`mat*`) and `@quasar/extras/material-icons-outlined` (`outlined*`). With `extras: []`, nothing resolves a ligature name any more.

## Delivered (PR #1603)

Measured with `quasar build`, `origin/dev` (`85ad0f71`) vs. branch tip:

|                                          | before     | after      | delta          |
| ---------------------------------------- | ---------- | ---------- | -------------- |
| `dist/spa` total (raw)                   | 5139.2 KiB | 4543.8 KiB | **−595.4 KiB** |
| icon webfont bytes in `dist`             | 634.0 KiB  | 0          | **−634.0 KiB** |
| …of which woff2 (what a browser fetches) | 277.2 KiB  | 0          | **−277.2 KiB** |
| entry JS+CSS, gzipped                    | 240.0 KiB  | 255.6 KiB  | +15.6 KiB      |

Net first-load transfer for a page that renders any icon: **≈ −261 KiB**, and the two `font-display: block` icon fonts leave the LCP critical path. The +15.6 KiB is the inlined SVG path data for the ~120 icons in use, mostly in the eagerly-loaded `navigation` chunk.

Scope: 248 call sites across 86 files were still on ligature names at rebase time; all are converted. Roughly 40 % of the sweep came from the original 2026-06 commits (rebased onto `dev`), the rest from a single sweep over current `dev`.

### Names Google dropped from the legacy set

Six names have no `@quasar/extras` SVG export. Five of them have **no ligature in the shipped webfont either** (verified against the font's GSUB table) — they were rendering as nothing in production, so the substitution fixes a latent bug rather than changing a working icon. Only `o_eco` was a real glyph before.

| name              | substitute                  | in the old webfont?         |
| ----------------- | --------------------------- | --------------------------- |
| `info_outline`    | `outlinedInfo`              | no                          |
| `manufacturing`   | `matPrecisionManufacturing` | no                          |
| `o_check_small`   | `outlinedCheck`             | no                          |
| `o_edit_document` | `outlinedEditNote`          | no                          |
| `o_table`         | `outlinedTableChart`        | no                          |
| `o_eco`           | `outlinedEnergySavingsLeaf` | yes — genuine visual change |

`o_eco`'s only call site is inside a `<!-- TEMPORARILY HIDDEN -->` block in `WorkspaceSelectorBar.vue`; commented-out markup was left as-is, so that substitute is not wired up yet.

### Guard

`frontend/tests/unit/svg-icons.spec.ts` replaces the per-area grep guards and the dev-only `iconMapFn` boot file this plan originally called for. It asserts (a) no source file references an icon by ligature name, (b) `quasar.config.js` keeps `extras: []` and the SVG icon set, (c) a converted component renders an inline `<svg>` and no `.material-icons` element. A runtime guard would add nothing: no icon name reaches `q-icon` from the backend or from i18n, so every call site is statically visible.

## Constraints (still binding when adding icons)

- **Do not touch `ModuleIcon` / `ModuleIconBox` / `module-icon` plugin usages** (`:name="module"`, `:name="row.module"`, …). Those render custom module SVGs (`src/assets/icons/modules/*.svg` via `import.meta.glob` raw import) and are unrelated to the webfonts.
- **Do not convert i18n keys, domain strings, or any non-icon `name:`/`icon:` property.** Many snake_case strings (`room_name`, `results_units_kg`, …) are translation keys.
- **Verification:** `cd frontend && make type-check` (a non-existent export name fails to compile), `make lint` (catches a half-done conversion as an unused import), and `npm run test-ct`.

---

## Background — current state (measured 2026-06-18)

Lighthouse on `…/2025/equipment`:

- `flUhRq6tz…woff2` — **126 KiB**, Material Icons, `font-display: block` (FOIT), on LCP critical path (~1,020 ms).
- `gok-H7zzD…woff2` — **152 KiB**, Material Icons Outlined, `font-display: block`, on LCP critical path (~1,249 ms).
- Both injected unconditionally by the top-level `extras: ['material-icons', 'material-icons-outlined']` in `quasar.config.js` — not by anything under `framework`.

Call-site inventory (frontend `src/`), re-measured against `origin/dev` on 2026-09-10:

- `120` distinct icon names over `248` call sites in `86` files across `components/`, `pages/`, `constant/`, `api/` (2026-06 figures were 111 / ~226 / ~80).
- `:name="…"` bindings that target `ModuleIcon`/`ModuleIconBox` are **out of scope** (custom SVGs).

---

## Conversion recipe — how to add an icon

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
5. **Derive the export name with the naming rule below.**
6. **Do not convert** `ModuleIcon`/`ModuleIconBox`/`module-icon` `:name` bindings, or non-icon properties.

After editing a file, the `name=`/`icon=`/`icon:` literal must be gone (it is now `:name`/`:icon` bound, or `icon: <import>`).

### What NOT to touch (explicit allow-list of survivors)

- `<ModuleIcon :name="…">`, `<ModuleIconBox :name="…">`, `module-icon` — custom module SVGs.
- `:name="icon"` where `icon` is a prop/variable (e.g. `EssentialLink.vue`, `VirtualSelectField.vue`) — already dynamic; the source value gets converted at its origin (config / computed), not here.
- Any `name:`/`icon:` that is not an icon (i18n keys, type discriminators, API fields).

---

## Naming rule

`o_x_y` → `outlinedXY` (from `@quasar/extras/material-icons-outlined`); every other name → `matXY` (from `@quasar/extras/material-icons`). A name that does not exist as an export fails `make type-check`, so there is nothing to memorise — the six names with no export at all are listed in the table above.

---

## Follow-ups

- Re-run Lighthouse on `…/2025/equipment` to confirm the icon-font payload and its FOIT are gone from the LCP critical path.
- Confirm the six substituted icons visually (table above); only `o_eco` changes a glyph that used to render, and its one call site is currently commented out.
- Sixteen of the touched `.vue` files were already over the 500-line component limit before this change; they each gain one import line and were deliberately not refactored here.
