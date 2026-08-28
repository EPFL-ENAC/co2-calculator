---
status: delivered
issue: 2497
last_updated: 2026-08-28
summary: chunk-load-reload e2e fails because the unmocked session check's real 404 toasts alongside the reload dialog — mock the session and wait for app readiness before firing the synthetic rejection
---

# 2497 — chunk-load-reload e2e: extra error toast alongside the reload prompt

## Root cause

`tests/integration/chunk-load-reload.spec.ts` navigates to `/` without
mocking any HTTP boundary — unlike every other integration spec. Against the
`npm run preview` webServer (no backend running), `GET /api/v1/session`
returns a real `404`. `src/api/http.ts`'s `afterResponse` hook treats any
non-401/403 error status as a generic failure and toasts it
(`"An error occurred: 404 Not Found"`). That toast is unrelated to the
chunk-load error the test simulates, but the assertion
(`expect(page.locator('.q-notification')).toHaveCount(0)`) can't tell the two
apart — confirmed by instrumenting the page's network/console log during a
run, which showed the 404 and the resulting `.q-notification` with exactly
that text.

`src/boot/sentry.ts`'s own chunk-load handling is correct: `toastFor()`
routes any `isChunkLoadError()` match to `notifyReloadOnce()` and returns
before ever calling `notifyError()`. Not an app bug.

## Second finding (test-only, not fixed here)

While verifying the mock fix, dispatching the synthetic rejection
immediately after `page.goto('/')` resolving was flaky (~50% failure) with
the session mocked: Playwright's CDP-level `pageerror` fired (proving the
browser saw the rejection), but neither the dialog nor a toast appeared —
meaning `boot/sentry.ts`'s `window.addEventListener('unhandledrejection', …)`
was not yet attached at that point. `unhandledrejection` is a point-in-time
event, not retryable, so a rejection that fires before the listener attaches
is silently dropped — the same failure mode #2194 exists to prevent, just at
boot instead of at a route change. This is a real gap in production too (an
early chunk-load failure right after page load could go unreported), but is
out of scope here: the fix below is a test-readiness wait, not an app change.
Filed for follow-up rather than actioned in this PR.

## Fix

`tests/integration/chunk-load-reload.spec.ts`:

- Mock `GET/POST /api/v1/session` to return `401` before `page.goto('/')`,
  so the unauthenticated session check never round-trips to a real (missing)
  backend and never triggers the generic-error toast.
- Wait for the rendered "Login" button (`getByRole('button', { name: /log
?in/i })`) before firing the synthetic `unhandledrejection` — a real
  readiness signal, not a fixed sleep, that reliably ensures boot listeners
  are attached first.

No app code changed for this issue.

## Test

The existing regression test itself is the coverage; it now passes
consistently across repeated runs (5/5 verified) with the fix in place, and
reliably reproduces the failure without it (session mock alone, no
readiness wait, was flaky; unmocked, it failed on the extra toast every
time).

## Deliverables

- [x] Session mock + readiness wait in `chunk-load-reload.spec.ts`
- [x] Verified stable pass (5 consecutive runs)
- [x] Flip to `delivered` on merge
