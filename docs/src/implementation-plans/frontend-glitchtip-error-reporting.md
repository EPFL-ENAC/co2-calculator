---
status: delivered
last_updated: 2026-06-18
title: "Frontend error reporting — minimal GlitchTip client (drop @sentry/vue)"
summary: "Replaces the @sentry/vue SDK with a ~2 KB dependency-free GlitchTip-compatible reporter (src/utils/glitchtip.ts). Captures Vue component, router, global, DOM-event, unhandled-rejection and ky 5xx errors. Fixes the two protocol bugs (missing envelope item header, missing DSN public key) that stopped events ingesting, and documents that the DSN must live in .env.local."
---

# Frontend error reporting — minimal GlitchTip client

## 1. Problem

The frontend shipped a full `@sentry/vue` integration plus a dead, half-written
custom reporter at `frontend/scripts/glitchtip.js`. Goals: keep crash visibility
only (no tracing/replay), shrink to a tiny dependency-free client, and capture
every error source. Two things blocked any event from reaching GlitchTip:

1. **DSN never loaded.** `quasar.config.js` loads only `.env.local` (gitignored)
   into `process.env.APP_*`. The DSN had been placed in `.env`, which neither that
   loader nor Vite reads, so `runtimeConfig.sentryDsn` was empty and init was
   skipped — `throw new Error(...)` went nowhere.
2. **The draft client could not ingest.** Its envelope omitted the mandatory
   `{"type":"event"}` item-header line, and it discarded the DSN public key during
   parse, so GlitchTip rejected the request.

## 2. Solution

A module-level singleton client speaking the Sentry envelope protocol (which
GlitchTip accepts). No-op without a DSN, so dev/CI stay silent.

**New — `frontend/src/utils/glitchtip.ts`:**

- `initGlitchTip({ dsn, release, environment, ignoreErrors, maxBreadcrumbs })`,
  `captureError(error, ctx?)`, `addBreadcrumb(message, category?)`.
- Protocol fixes vs the draft: keeps the public key and sends it as
  `?sentry_key=` (+ `dsn` in the envelope header); emits the 3-line envelope
  (envelope header / item header / payload); breadcrumbs as `{ values: [...] }`;
  minimal Chrome+Firefox stack parser → `stacktrace.frames` (oldest-first);
  per-capture `mechanism { type, handled }`.
- Retained from the draft: consecutive-error dedupe, best-effort `localStorage`
  offline buffer + flush on init, `keepalive` POST.

**Rewired — `frontend/src/boot/sentry.ts`** (boot slot name kept as `sentry`;
the `APP_SENTRY_DSN` env name is wired through `runtime.ts`, `quasar.config.js`,
`docker/entrypoint.sh` and Helm — unchanged). Calls `initGlitchTip` when a DSN is
set and wires every source to `captureError`, keeping the existing `ignoreErrors`
list and user-facing toasts:

| Source                          | Hook                                         | mechanism                              |
| ------------------------------- | -------------------------------------------- | -------------------------------------- |
| Vue component errors            | `app.config.errorHandler`                    | `vue`                                  |
| Vue Router (chunk load, guards) | `router.onError` _(new)_                     | `vue-router`                           |
| Global synchronous / DOM-event  | `window 'error'` (ResizeObserver suppressed) | `onerror`                              |
| Unhandled promise rejection     | `window 'unhandledrejection'`                | `onunhandledrejection` (handled:false) |
| ky HTTP 5xx                     | `afterResponse` in `src/api/http.ts`         | `generic`                              |

**Removed:** `@sentry/vue` dependency (`package.json`) and both its usages
(`boot/sentry.ts`, `api/http.ts`'s lazy `captureMessage`); deleted the dead
`scripts/glitchtip.js`. No prod Docker/Helm change — `docker/entrypoint.sh` writes
any `APP_*` var into `injectEnv.js` generically.

**Trade-off (in scope):** loses performance tracing / slow-route visibility,
session replay, and server-side source-map frame resolution. Scoped to "errors
only".

## 3. Configuration

Dev: `cp .env .env.local` (DSN must be in `.env.local` — `.env` is not loaded).
Prod: `APP_SENTRY_DSN` from the pod env via Helm → `injectEnv.js`.

## 4. Verification

- `make type-check` (vue-tsc) and `npm run lint` — both green; no `@sentry`
  imports remain.
- Manual (`quasar dev`): console `throw new Error('aefaef')` produces a
  `POST …/api/<projectId>/envelope/?sentry_key=…` → 200 and a visible GlitchTip
  event. Exercise each source (component throw, `Promise.reject`, route error,
  backend 500); confirm ResizeObserver / `AbortError` / `Failed to fetch` are
  not sent.
