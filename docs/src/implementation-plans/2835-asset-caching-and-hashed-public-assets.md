---
status: delivered
issue: 2835
last_updated: 2026-09-17
title: "Asset caching: hashed immutable, unhashed revalidated, public/ assets through Vite"
summary: "Travel map broke because maplibre's ES-module worker was served as application/octet-stream and, under 1.4.13, cached as immutable in that broken state. Fix in three layers: register mjs/csv MIME types and bundle the worker with Vite (#2837, #2838); nginx gives immutable only to Vite-hashed names and revalidates everything else; templates, fonts, favicons, logo and login image move from public/ to src/assets so a replaced file gets a new URL. Also the cache side of #2812 (stale CSV template)."
---

# Asset caching: hashed immutable, unhashed revalidated, public/ assets through Vite

## Problem

- maplibre-gl 6 ships its worker as a separate ES module that imports a
  sibling `maplibre-gl-shared.mjs`. The nginx base image's `mime.types` has no
  `mjs` entry, so both were served as `application/octet-stream` and Chrome
  refused the module (#2835, map missing on Travel).
- 1.4.13 added an `.mjs` location with a one-year `immutable` header, so the
  broken octet-stream response was cached for a year. A header fix alone
  cannot reach those browsers.
- The same shape hit CSV templates (#2812): `public/templates/*.csv` had no
  `Cache-Control` at all, so browsers cached them heuristically and some users
  kept the old external AI template after it was replaced.
- `public/` images, fonts and favicons were stamped `immutable` under stable
  names. Replacing one under the same name left returning users on the old
  file for a year.

## Decisions

1. **MIME types are registered once at http level** with a `types { }` block
   after `include mime.types`: `application/javascript mjs; text/csv csv;`.
   Stock nginx 1.30 has neither.
2. **Only Vite-hashed names get `immutable`.** The hash is exactly 8 base64url
   chars (`-`/`_` included), matched by a quoted regex
   `"-[A-Za-z0-9_-]{8}\.(ext…)$"`. Exact count: an open-ended `{8,}` also
   matched `maplibre-gl-shared.mjs` through `-gl-shared`. Unquoted braces are
   parsed by nginx as a block and the server refuses to start.
3. **Everything else revalidates** with `no-cache, must-revalidate`. The split
   stays even though the build now emits no unhashed asset: it is the guard
   for the next unhashed copy someone adds.
4. **The worker is bundled by Vite** via `?worker&url` in `TripsMap.vue`. The
   shared chunk is inlined into one hashed file, the afterBuild copy in
   `quasar.config.js` is gone, and the worker URL changes, which is what
   evicts the polluted cache entries.
5. **`public/` assets move to `src/assets`** so every reference is
   content-hashed: `index.html` favicon and font preload links, SCSS `url()`
   for fonts and the login background, an explicit `import` for the logo,
   and `import.meta.glob` with `?url&no-inline` for the templates. `url` is
   needed because `.csv` is not a Vite asset type; `no-inline` because Vite
   inlines anything under 4 KB as a data URI. `a.download` keeps the plain
   template file name for the user.
6. **`public/` keeps only `injectEnv.js`** (runtime config, served from
   `/tmp` by an exact-match location) and a plain `favicon.ico` for clients
   that probe `/favicon.ico` without reading `index.html`. `index.html` links
   it as `favicon.ico?v=<%= appVersion %>` (Quasar `htmlVariables`, fed by the
   same git SHA as `APP_VERSION`), and `location = /favicon.ico` caches it
   for a day: releases bust it through the query, bare probes wait a day.
7. The glob lives in a browser-only leaf, `constant/templateAssets.ts`, not
   in `templateMapping.ts`: the latter is imported by a Node-side Playwright
   test that cannot evaluate `import.meta.glob` (same constraint as
   `mergeLivePipelineJob`). The leaf keys URLs by file name and throws at
   boot if any `SHIPPED_TEMPLATES` entry is not bundled, so a wrong glob
   path fails the first page load rather than a user's click.
8. **No `expires` directives.** `expires` and `add_header Cache-Control` on
   the same location emit two `Cache-Control` headers; only `add_header`
   remains.
9. **The template directory is checked from both sides.**
   `backend/tests/unit/test_shipped_csv_templates.py` runs every CSV on disk
   through the ingestion parser (it lives in the backend because the parser
   does). `frontend/tests/unit/template-mapping.spec.ts` asserts the mapping
   and the directory agree exactly via the exported `SHIPPED_TEMPLATES`. A
   moved directory, an orphan file or a dangling entry (the old
   `equipments_template.csv` default, removed here) fails both suites.

## Delivered

- #2837: MIME registration and the hashed/unhashed split for JS/CSS/MJS.
- #2838: worker bundling, split extended to every asset type plus `csv`,
  `public/` assets hashed through Vite, unreferenced `public/` leftovers
  removed, backend template test and frontend template test repointed at
  `src/assets/templates`.

## Verification

Build served from `nginxinc/nginx-unprivileged:stable-alpine-slim` against
`dist/spa`: the only unhashed files are `index.html`, `injectEnv.js` and
`favicon.ico`; 22 of 22 templates emitted as hashed files and referenced
from the chunk; hashed js/csv/png/svg/woff2 answer `immutable` with the
right Content-Type; `index.html` and `/travel` answer `no-cache`.

## Not done

- A `location ^~ /assets/` prefix rule would replace the regexes but would
  re-stamp `immutable` on any unhashed file copied into `assets/`, which is
  exactly the failure this plan fixes. Rejected.
- Extensions outside the two lists (`.wasm`, `.webmanifest`) fall through to
  `location /` with no `Cache-Control`. Add them to both lists when one ships.
