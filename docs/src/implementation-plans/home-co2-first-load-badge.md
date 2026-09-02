---
status: delivered
issue: 673
last_updated: 2026-09-02
summary: Build-time CO₂ first-load badge in the homepage calculator header
---

# Homepage CO₂ first-load badge

**Status:** delivered (2026-08-27)
**Branch:** `feat/673-impactconsumption-of-webapp`

Show the webapp's own carbon footprint as a small badge + tooltip on the
homepage, computed once at build time. No Lighthouse involvement; the nightly
`lighthouse.yml` cron is untouched.

## Decision

- **Build-time constant, not live measurement.** The SPA build emits a tiny
  `dist/spa/index.html` bootstrap plus content-hashed chunks, so "weight of a
  visit" = index.html + the first-load assets it references (entry module
  script, `modulepreload` chunks, stylesheets).
- **Per-byte constant** from websitecarbon.com (`1.94e-7` g CO₂/byte),
  overridable via `CO2_G_PER_BYTE`.
- **First-load semantics**: copy says the number is the first, uncached load;
  later visits are served from cache.
- **No silent fallback**: missing meta tag (dev server) → no badge rendered.

## Shipped

- `frontend/scripts/inject-co2.mjs` — post-build: gzips (level 9) index.html +
  referenced first-load assets, adds the raw size of every woff2 font those
  preload or reference (woff2 is already compressed), sums bytes, injects an idempotent
  `<meta name="co2-first-load" content="{mg}|{kb}">`, logs a one-line report.
  Missing referenced asset or missing `</head>` throws.
- `frontend/quasar.config.js` — `build.afterBuild` runs
  `scripts/inject-co2.mjs`, so every `quasar build` (npm script, Makefile,
  Docker, CI, or typed directly) carries the meta.
- `frontend/src/composables/useCo2FirstLoad.ts` — parses the meta tag,
  returns rounded `{ mg, kb }` or `null`.
- `frontend/src/components/organisms/workspace-selector/WorkspaceSelectorBar.vue`
  — borderless green leaf-icon text + `q-tooltip` on the same row as the
  RoleAccessBadge, separated by a thin vertical rule; rendered only when the
  composable returns a value. The affiliation breadcrumb stays below that
  row. (Bar is used on the homepage only.)
- `frontend/src/i18n/home.ts` — `home_co2_badge_label` / `home_co2_tooltip`
  (EN/FR).
- `frontend/quasar.config.js` — dev-only Vite hook (`apply: 'serve'`) copies
  the co2-first-load meta from `dist/spa/index.html` into the dev server's
  HTML, so the badge is also visible under `quasar dev` (with the number from
  the last production build). No dist or no meta → nothing injected.
- `frontend/Makefile` — `make dev` runs `npm run build` once when
  `dist/spa/index.html` has no co2-first-load meta, so the badge shows on a
  fresh checkout without a manual build.

## Caveats

- Counts what index.html references (entry + preloads + CSS) plus the woff2
  fonts preloaded from index.html or declared in the first-load CSS (Suisse
  Intl ×3, Material Icons, Material Icons Outlined); excludes `injectEnv.js`
  and the lazily-loaded route chunks. The HomePage
  route's own lazy chunk is small; adding it later means also summing
  `HomePage-[hash].{js,css}`.
- With fonts (2026-09-02): 574.9 KB across 47 files + 5 fonts (328.9 KB of
  which are fonts) → ≈114 mg CO₂ per first load.
