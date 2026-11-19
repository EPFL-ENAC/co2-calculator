---
status: in-progress
issue: 3298
last_updated: 2026-11-17
summary: "Record of each idea explored for the first screen on 2026-11-17: ten parallel explorations, the logo attempts, the architecture options, and the measurements. It says what was kept, what was dropped, and what to look at again."
---

# First screen: record of the explorations (#3298)

This page keeps the full result of each idea that was explored on
2026-11-17, so that a later reader can look at one again. The plan of
the work that was kept is in
[3298-first-screen-load.md](./3298-first-screen-load.md).

Each exploration has a local branch in the main repository. On
2026-11-17 these branches were not pushed. Before you delete a branch,
push it or copy its commit.

## How the numbers were made

- Build: `./node_modules/.bin/quasar build`, then
  `node build/prepare-preview.mjs`, which writes the files that nginx
  serves in the container.
- Lighthouse, mobile preset, on `/en/login`. The first measurements used
  `/` and were wrong for the static first frame, which shows on a login
  URL only.
- The EPFL font server answers 403 to an origin that it does not know.
  Chrome resolved the dev host name to the local server
  (`--host-resolver-rules`). The page then had the origin of the dev
  site, and the fonts loaded.
- "Simulated" is the default Lighthouse throttling, a model. "Slow 4G"
  is applied throttling (`--throttling-method=devtools`), a real
  waterfall.
- "First-screen payload" is the gzip size of the files that `index.html`
  references. It does not count a file that a script asks for later.
- Signed-in pages used a local backend, the test login
  (`calco2.user.principal`), and a proxy that sent `/api/*` to it.

## Why the #3244 branch lost 12 points

The JavaScript did not grow: 327 KB on the branch against 330 KB on
`dev`. The largest paint changed from the title text to the logo.

| Build        | Score | Largest paint | Largest element |
| ------------ | ----- | ------------- | --------------- |
| `dev`        | 98    | 1.96 s        | the title text  |
| #3244 branch | 86    | 4.21 s        | the logo image  |

On `dev` the fonts were preloaded and the logo was in the bundle. On
the branch the title paints first in the fallback font, which is
narrower: 4368 px² against 4391 px² for the logo. So the logo became
the largest paint. The Lighthouse model charges an element that the app
draws late for each script that loaded before it.

## Attempts on the logo

All on the #3244 branch, mobile preset, seven runs each.

| Attempt                                     | Simulated largest paint | Observed largest paint | Kept |
| ------------------------------------------- | ----------------------- | ---------------------- | ---- |
| No change                                   | 4.22 s                  | 294 ms                 |      |
| `<link rel="preload">` for the logo         | 4.22 s                  | 275 ms                 | no   |
| Eager load and no fade on the `q-img`       | 4.22 s                  | 149 ms                 | yes  |
| Logo in the static page, shown before mount | 4.06 s                  | 107 ms                 | no   |
| The same, with `fetchpriority="high"`       | 4.22 s                  | not measured           | no   |
| Login card title at 28 px                   | 1 loss in 7 runs        | not measured           | no   |

The model did not move for an image, in any form. Only text as the
largest paint moved it, which is exploration 7.

## The ten explorations

Each one started from the #3244 tip (`e4526b31d`) in its own worktree.
The table gives the first-screen payload that each agent measured, and
the score that the orchestrator measured after, on five runs.

| No. | Idea                              | Branch                       | Commit      | Payload              | Requests | Score                  |
| --- | --------------------------------- | ---------------------------- | ----------- | -------------------- | -------- | ---------------------- |
|     | Baseline                          | #3244                        | `e4526b31d` | 327.1 KB             | 45       | 86                     |
| 1   | One text file for each language   | `perf/3244-i18n-lazy`        | `e06a4c420` | about 299 KB         | 50       | 88                     |
| 2   | Cut eager imports                 | `perf/3244-eager-imports`    | `fb3d40932` | about 291 KB         | 39       | 88                     |
| 3   | Lighter Quasar                    | `perf/3244-quasar-treeshake` | `6ed6d66f3` | 317.4 KB             | 44       | 86                     |
| 4   | Defer the boot files              | `perf/3244-defer-boot`       | `07585c818` | 327.1 KB             | 44       | 86                     |
| 5   | Chunk shapes                      | `perf/3244-chunking`         | `99c05ad1d` | 310.9 KB             | 3        | 91                     |
| 6   | Less render-blocking CSS          | `perf/3244-critical-css`     | `f4e1a056d` | 319.0 KB             | 45       | 86                     |
| 7   | Static first frame with text      | `perf/3244-static-shell`     | `1c2108d91` | 327.1 KB             | 45       | 100                    |
| 8   | Startup files inlined in the HTML | `perf/3244-inline-runtime`   | `e8f093159` | two requests fewer   | 43       | 86                     |
| 9   | Precompression and preconnect     | `perf/3244-transport`        | `30c265a1d` | 326.3 KB on the wire | 45       | not measurable locally |
| 10  | Account by library                | `perf/3244-dependency-diet`  | `63c6a2ddf` | 326.2 KB             | 45       | 86                     |

### 1. One text file for each language

`src/i18n/index.ts` loads each text module eagerly and builds both
languages, in one 68 KB chunk. A new Vite plugin
(`build/i18n-locale.mjs`) splits each `{ en, fr }` pair at build time.
The app waits for the texts of the active language before it mounts.

- Result: about 28 KB less. One language is still about 35 KB, because
  it holds all 1765 texts of the app, and the login page needs a few.
- Cost: five requests more and one extra round trip, because the text
  chunk is a dynamic import.
- Risk: it sets `chunkOptimization.mergeCommonChunks: false` for the
  whole build. Without it, the bundler moved a helper into the chart
  chunk and the first screen grew to 442 KB. This option conflicts with
  exploration 5.
- Not merged. To look at again: split the texts by page, so that
  `tooltips.ts` (85 KB of source) loads with the pages that use it.

### 2. Cut eager imports

`routes.ts` imported the home page and the main layout statically.
So the login page loaded the header, both sidebars, the planner table
and the module icons. The layout parts became lazy, and a guard loads
them after a session exists.

- Result: the script reports 263.8 KB. The true total for login is
  about 291 KB, because the login card uses a select component that now
  arrives with the lazy login chunk.
- Left alone, each with a reason: the stores (the guards need them), the
  Quasar inputs of the dialog plugin, and the `navigation` chunk (it
  holds vue-i18n and each icon of the app).
- Merged. It reversed a comment in `routes.ts` that shipped the layout
  with the entry on purpose. It also caused a layout shift on signed-in
  pages, fixed later (see the plan).

### 3. Lighter Quasar

The full Quasar stylesheet became a list of the parts in use, without
36 parts. Three unused plugins left the configuration (`LocalStorage`,
`SessionStorage`, `Meta`).

- Result: CSS 40.3 to 32.1 KB, JavaScript 286.9 to 285.3 KB.
- Proof: no dropped class in `src`, tests or Storybook. The built CSS
  lost 618 rules and gained none.
- Finding: the dialog plugin costs 12.3 KB and seven requests, for one
  user, the reload prompt. That became its own ticket and is merged.
- Not merged: it overlaps with exploration 6, which has a check script.
  To take from it: the removal of the three plugins.

### 4. Defer the boot files

- Finding: the reporter is about 2 KB of the chunk named `glitchtip`.
  The other 8 KB is Quasar screen and notification code. Moving the
  reporter later saves about 1.5 KB and loses the breadcrumbs of the
  first requests, so it stayed.
- Change on the branch: Matomo loads after the first route and an idle
  moment. A visitor who leaves within about 3 seconds is then not
  counted.
- Finding kept for later: Quasar loads each boot file with a dynamic
  import, which costs one round trip. That became a ticket and is
  merged.
- Not merged.

### 5. Chunk shapes

The bundler is Rolldown, not Rollup. `experimentalMinChunkSize` does not
exist, and `manualChunks` is deprecated.

| Setting                                       | Requests | KB gzip |
| --------------------------------------------- | -------- | ------- |
| Baseline                                      | 45       | 327.1   |
| One `$initial` group                          | 2        | 312.6   |
| Kept: initial `node_modules` and an app group | 3        | 310.9   |
| Vendor group only                             | 11       | 311.9   |
| `experimentalInlineCommonChunks`              | 16       | 333.5   |
| `cssCodeSplit: false`                         | 44       | 345.5   |
| `modulePreload: false`                        | 45       | 324.9   |
| Target `baseline-widely-available`            | 44       | 323.5   |

- Merged. The newer target saves 3.6 KB and ends support below Chrome
  and Edge 111, Firefox 114 and Safari 16.4. That is a product decision
  and was not taken.
- Deploy churn: the entry gets a new name on each build, which renames
  60 of 131 files. The baseline did the same (66 of 173).

### 6. Less render-blocking CSS

- Breakdown of the 40.6 KB entry stylesheet: Quasar 36.9 KB (91%), the
  project layers 1.9 KB, page styles 3.2 KB.
- Change: `src/css/_quasar-base.scss` lists the Quasar parts in use,
  without 29 parts. `scripts/check-quasar-css.mjs` fails the type check
  for a Quasar component in use that has no stylesheet.
- Result: 40.3 to 32.1 KB. Still three blocking stylesheets.
- Rejected inside it: a hand-made critical CSS split. The body is empty
  until the app mounts, so non-blocking CSS can only add a flash.
- Finding: only `--theme-accent` must exist before the first paint.
- Not merged. First candidate to merge next, because of the check
  script. It needs a look at several pages in a browser.

### 7. Static first frame with text

See the plan. The first measurement on `/` showed no gain. On
`/en/login` it gave a score of 100 and a largest paint of 1.50 s alone,
and 1.35 s with explorations 2 and 5.

- The first-frame title is 28 px. At the 24 px of the card title, the
  English title is 4368 px² and the logo 4391 px², so the logo wins.
- Merged, with a later fix: the app waits two animation frames before
  it mounts. Before that fix, the first frame was the largest paint in
  2 runs of 5. After it, in 12 runs of 12.

### 8. Startup files inlined in the HTML

`entrypoint.sh` reads the built page and writes `/tmp/index.html` with
the theme in a `<style>` tag and the values in a `<script>` tag. nginx
serves that file. `/theme.css` and `/injectEnv.js` then return 404.

- Result: two requests fewer, one of them render-blocking.
  `index.html` grows from 1.2 to 1.8 KB gzip.
- Rejected inside it: nginx `sub_filter` and SSI, because only nginx
  runs them, so no test covers them. The logo is not inlined: an SVG of
  the operator can then run script in the origin of the app.
- Open points: read the escape of `<` in the values, which stops a
  value from closing the script tag. The dev server and the tests keep
  the files as files, so the inline path runs in the container only.
- Not merged. Second candidate, because the first paint waits 1.2 s for
  the stylesheets on Slow 4G.

### 9. Precompression and preconnect

- nginx 1.30 in the image has `gzip_static` and no brotli module.
- First screen: 330.6 KB as nginx served it, 326.3 KB with gzip 9
  files, 279.5 KB with brotli 11.
- Change on the branch: gzip files at build time, and a `Link`
  preconnect header for the font host, written by `entrypoint.sh` into
  an nginx include.
- Finding: the three startup files get a new ETag at each container
  start, so each rollout downloads them again.
- Not merged as it is. The brotli ticket replaced the compression part
  and is merged. The preconnect header is still a candidate.

### 10. Account by library

Share of the first-screen JavaScript, in source size before minify.

| Part                                     | Share |
| ---------------------------------------- | ----- |
| Quasar                                   | 30%   |
| The texts of the app (`src/i18n`)        | 20%   |
| Vue                                      | 12%   |
| App code (constants, components, stores) | 18%   |
| vue-i18n and its compiler                | 7%    |
| vue-router, ky, Pinia, icons             | 9%    |

- No duplicated library, and no chart, map, date or CSV library on the
  first screen.
- Change on the branch: vue-i18n without its three template components
  (0.9 KB).
- Three decisions left, all with a small gain and a real risk: drop the
  message compiler (4.4 KB, breaks the placeholders), drop the `es2019`
  target (1.1 KB), replace `ky` with `fetch` (up to 6 KB).
- Not merged. The account is the useful part.

## Architecture options

| Option                        | Verdict                                         |
| ----------------------------- | ----------------------------------------------- |
| One SPA, on a diet            | done in Part 1                                  |
| Static first frame            | done, it gave the score                         |
| A light public page for login | not built: the first frame gave the same result |
| One SPA for each area         | rejected                                        |
| Server rendering              | rejected: production needs a Node server        |

One SPA for each area (login, back office, explore, planner, main app)
does not shrink the first screen. The areas are already separate lazy
files. What each page shares is the libraries (123 KB) and the app
entry (90 KB), and a second build carries the libraries a second time.

| Area                 | Files                        | Size gzip        | On the first paint |
| -------------------- | ---------------------------- | ---------------- | ------------------ |
| Each page            | libraries, entry, stylesheet | 123 + 90 + 38 KB | yes                |
| Results              | page and chart library       | 189 + 177 KB     | no                 |
| Maps                 | map library and worker       | 292 + 146 KB     | no                 |
| Module pages         | module sections              | 41 KB            | no                 |
| Planner, back office | pages                        | 8 to 20 KB each  | no                 |

The light public page stays an option. It needs three things:

- A second HTML entry in the same build.
- A login screen without Quasar.
- A preload of the app files during the visit to the identity provider.

## The load chain

The login page on Slow 4G, before Part 1 of the chain work.

| Step                         | Starts  | Ends    |
| ---------------------------- | ------- | ------- |
| HTML                         | 0 ms    | 573 ms  |
| Entry scripts and stylesheet | 607 ms  | 2457 ms |
| Three boot files, 3.3 KB     | 2529 ms | 3125 ms |
| Session call                 | 3143 ms | 3712 ms |
| Login page code, 12 files    | 3717 ms | 5430 ms |
| Logo and illustration        | 5468 ms | 6041 ms |

Each round trip costs about 600 ms. A Chrome trace of the maintainer
showed the same chain (Slow 4G, CPU 20 times slower). The title showed
at 2.0 s and the card at 7 s.

Signed-in pages, Slow 4G, three runs.

| Page    | Build  | First paint | What it waits for                         |
| ------- | ------ | ----------- | ----------------------------------------- |
| Home    | #3244  | 8.66 s      | session, files, two API calls in sequence |
| Home    | branch | 8.82 s      | the same                                  |
| Results | #3244  | 11.62 s     | the results page and the chart library    |
| Results | branch | 11.75 s     | the same                                  |

## To look at again, in this order

1. Exploration 6, the smaller Quasar stylesheet.
2. Exploration 8, the theme and the values in the HTML.
3. Part 2 of the plan, the signed-in first paint.
4. The texts by page (exploration 1, second step).
5. The preconnect header for the font host (exploration 9).
6. Group the 12 files of the login route into one or two.
7. A higher limit for the nightly Lighthouse job, which is 60 today.
