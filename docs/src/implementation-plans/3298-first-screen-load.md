---
status: in-progress
issue: 3298
last_updated: 2026-11-17
summary: "The login page paints its title from index.html and loads its code in parallel. The first screen needs 3 files in place of 45. Lighthouse mobile goes from 86 to 100. The signed-in pages are Part 2 and not started."
---

# Fast first screen: login page and first paint (#3298)

The app draws each page with JavaScript, so a visitor sees nothing until
the bundle runs. This plan covers the first screen. Part 1 is the login
page and is built on the branch `perf/first-screen`, on top of #3244.
Part 2 is the first page of a signed-in user and is not started.

The record of each idea that was explored, with its numbers, is in
[3298-first-screen-explorations.md](./3298-first-screen-explorations.md).

## Results of Part 1

Login page, local production build, Lighthouse mobile preset, median.

| Measure                      | #3244 branch | This branch |
| ---------------------------- | ------------ | ----------- |
| Lighthouse score             | 86           | 100         |
| Largest paint, simulated     | 4.21 s       | 1.35 s      |
| Login card complete, Slow 4G | 6.0 s        | 4.4 s       |
| Logo downloaded, Slow 4G     | 6.0 s        | 2.4 s       |
| Requests                     | 63           | 30          |
| First-screen files, gzip     | 327 KB       | 235 KB      |
| First-screen files, brotli   | not served   | 199 KB      |
| Round trips before the card  | 5            | 3           |

Signed-in pages keep their numbers: the home page paints at about 9 s
and the results page at about 12 s on Slow 4G, before and after.

## Decisions

- The login title paints from `index.html`. A static element `#shell`
  shows only while `#q-app` is empty, so no script removes it. An inline
  script fills it on a `/<lang>/login` URL only, in the language of the
  URL. The text comes from `src/i18n/login.ts` through `htmlVariables`
  of `quasar.config.js`, so the text has one home.
- A last boot file, `src/boot/first-frame.ts`, waits two animation
  frames before the app mounts, 100 ms at most. Without it, a fast
  connection lets the app mount before the browser shows the first
  frame. The page then starts blank, and the largest paint is an element
  that the app draws.
- The header and the two sidebars are not in the entry bundle.
  `src/router/authenticatedShell.ts` loads them after a session exists
  and keeps the loaded components. `MainLayout.vue` renders them as
  plain components. An async wrapper drew them one frame late and moved
  the page content (layout shift 0.389 on the results page).
- The entry is two JavaScript files: `vendor` (the libraries that each
  page needs) and the app entry. Rolldown `codeSplitting.groups` makes
  them. The chart and map libraries stay lazy.
- Quasar imports each boot file after the entry runs. A build plugin
  adds one `modulepreload` link for each boot chunk, so they download
  with the entry.
- On a login URL, the app starts the login page import before the
  session call answers, and `index.html` preloads the logo and the login
  illustration.
- The reload prompt after a deploy is a notification with a "Reload"
  button and a "Later" button. The dialog plugin was its only user, and
  it cost 19 KB on each first load. The prompt no longer blocks the page
  behind it.
- The image holds a `.gz` file (gzip 9) and a `.br` file (brotli 11) for
  each text file, made by `build/precompress.mjs` at build time. nginx
  has no brotli module: a `map` on `Accept-Encoding` and an internal
  location serve the `.br` files with the content type of the original.

## Tests

- `tests/integration/login-shell.spec.ts`: the first frame shows the
  title in both languages, stays empty on other pages, hides after the
  app mounts, and is the largest paint.
- `tests/integration/authenticated-shell.spec.ts`: the login page does
  not request the layout files, and the header is in the first frame of
  the page content.
- `tests/integration/boot-chunks.spec.ts` and
  `login-parallel.spec.ts`: the preload links and the parallel requests.
- `tests/integration/chunk-load-reload.spec.ts`: the reload prompt as a
  notification.
- `docker/test-nginx.sh`: 68 assertions on the real nginx image for the
  brotli and gzip negotiation.

On 2026-11-17 the branch passed 948 component tests and 139 e2e tests.

## Part 2, not started

The signed-in home page waits for a chain: the session call, then the
layout and page files, then the year configuration call, then the
workspace call. The proposal, in this order:

1. Run the year configuration call and the workspace call in parallel.
2. Paint the header and the page frame before the data arrives.
3. Start the session call from the HTML.

## Caveats

- The first frame shows on a login URL only. A visitor who opens `/`
  gets the redirect to login from the app, so `/` scores 91, not 100.
- An institution with a taller logo can make the logo larger than the
  title. The first frame then loses the largest paint.
- The results page scores 80 in the mobile simulation, against 95
  before. The real first paint did not change (11.6 s and 11.8 s on
  Slow 4G).
- Brotli is not confirmed behind the load balancer. The deployed chain
  passes gzip through unchanged (tested on dev on 2026-11-17).
- The local measurements use an HTTP/1.1 server. Production uses HTTP/2,
  so the wait of the session call behind the login files is smaller
  there.
