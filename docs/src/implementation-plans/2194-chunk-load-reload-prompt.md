---
status: delivered
issue: 2194
last_updated: 2026-08-28
title: "Stale-chunk alert noise + blocking reload prompt"
summary: "Every release paged the team over stale-chunk load errors (expected post-deploy SPA noise, already diagnosed in #2194) because only one of four error-capture sites in boot/sentry.ts special-cased them. Extends the existing ignoreErrors filter so they never reach GlitchTip, and upgrades the dismissible reload toast to a persistent, blurred-backdrop Dialog with Reload/Later actions."
---

# Stale-chunk alert noise + blocking reload prompt

## 1. Problem

After each deploy, browser tabs left open from before the release hold stale
chunk hashes — `dist/spa` is replaced wholesale on every deploy, so a lazy
`import()` for a route or async component 404s. `frontend/src/boot/sentry.ts`
already detected this (`isChunkLoadError`) and showed a "new version
available, reload" toast, but only from the `router.onError` capture site.

Two gaps:

1. `router.onError` reported the event to GlitchTip **before** checking
   `isChunkLoadError` — the one path that detects this condition still
   alerted on it every time, on every release.
2. The other three capture sites (`app.config.errorHandler`,
   `window.onerror`, `window.onunhandledrejection`) never checked
   `isChunkLoadError` at all. A chunk failure from a non-route dynamic import
   (an async component, not a route) only ever reaches `unhandledrejection`,
   which reported it _and_ showed the generic red error toast instead of the
   reload prompt.

Net effect: every release generated a burst of GlitchTip email/Teams alerts
for a condition that already has a working, one-click user-facing recovery —
and part of the time the recovery UI didn't even show.

## 2. Solution

Two mechanisms, one job each, in `frontend/src/boot/sentry.ts`:

- **Reporting** — extracted the chunk-match regexes (`chunkLoadPatterns`)
  shared by `isChunkLoadError()` and appended into the existing
  `ignoreErrors` list (the same "known, not-actionable" bucket
  `ResizeObserver loop`/`NetworkError`/`AbortError` already live in).
  `matchesAny()` in `glitchtip.ts` is the single chokepoint every
  `captureError()` caller funnels through (including `api/http.ts`), so this
  covers all four sites — and any future one — without per-caller guessing.
- **Toast routing** — a `toastFor(err, message, caption?)` helper wraps
  `notifyError`: if `isChunkLoadError(err)`, show the reload prompt instead.
  Replaces the 3 `notifyError(...)` calls that didn't already special-case
  chunk errors. `router.onError` already gated correctly and needed no
  change.
- **Reload prompt UX** — `notifyReloadOnce()` moved from a dismissible sticky
  `Notify` toast to a `Dialog.create` with `persistent: true` (blocks
  Escape/backdrop-click dismiss) and two actions: **Reload** and **Later**.
  A blurred backdrop (`.reload-prompt-dialog .q-dialog__backdrop`,
  `frontend/src/css/05-quasar-overrides/_q-dialog.scss`) makes it visually
  distinct from a passive toast. Reload-only (no escape hatch) was
  considered and rejected: the dialog is reachable from every capture site,
  not just post-deploy chunk failures, and `ignoreErrors` already treats
  `NetworkError`/`Failed to fetch` as expected transient blips — a
  Reload-only trap would force a mid-form user to lose unsaved work on an
  ordinary network glitch. "Later" resets the single-shot guard so the
  prompt can reappear on a later failure in the same session.

New i18n key: `later` (`frontend/src/i18n/common.ts`, en + fr). Reuses the
existing `new_version_available`/`reload` keys.

## 3. Explicitly skipped

`#2194`'s own decision text floated a proactive version-poll (periodic
`index.html` fetch, compare entry-chunk hash) if the occurrence threshold was
hit. Skipped here: it solves neither the alert-noise nor the toast-severity
problem, and adds a polling loop with its own staleness edge cases. Revisit
if users start hitting broken routes/blank screens _before_ the reactive
prompt fires — this change doesn't touch that failure mode.

## 4. Test

`frontend/tests/integration/chunk-load-reload.spec.ts` — dispatches a real
unhandled rejection with a stale-chunk message (the Playwright `webServer`
runs `npm run preview` against the production build, so the
`import.meta.env.DEV`-gated `window.__gtTest` trigger isn't available) and
asserts: the persistent dialog appears with Reload/Later actions, Escape and
a backdrop click do not dismiss it, and no generic error toast
(`.q-notification`) appears.

The "no GlitchTip event sent" half isn't independently assertable in that
spec — `initGlitchTip` is a no-op with no DSN configured in the test env, so
a network-call counter would pass vacuously either way. That guarantee rests
on `matchesAny()` matching the extended `ignoreErrors` list.

## 5. Follow-up (not code)

The already-open GlitchTip issues from past stale-chunk noise won't
auto-resolve — new occurrences stop, but historical ones stay open until
manually resolved/ignored in the GlitchTip UI.
