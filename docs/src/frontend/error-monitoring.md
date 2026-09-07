---
status: delivered
last_updated: 2026-05-19
summary: Frontend error monitoring with self-hosted GlitchTip (Sentry-compatible).
---

# Frontend Error Monitoring

The frontend reports uncaught JavaScript errors, server 5xx
responses, and a 5% sample of route navigations to **GlitchTip**,
EPFL ENAC-IT's self-hosted, Sentry-compatible error tracker. We use
GlitchTip rather than hosted Sentry so error data stays on EPFL
infrastructure. Wired in issue #344 — see the
[implementation plan](../implementation-plans/344-frontend-error-monitoring.md).

## Access

- **Dashboard:** [enac-it-glitchtip.epfl.ch](https://enac-it-glitchtip.epfl.ch).
  Sign in with a dedicated GlitchTip account (not EPFL SSO). Ask
  **nicdub** for an account and project membership.
- **Runbook:** ENAC-IT's
  [Sentry self-host via GlitchTip](https://www.notion.so/enacit4r/Sentry-Self-Host-via-Glitchtip-35e53a25eee880448351e452829897cd)
  Notion page — how the server is operated.
- **Product docs:** [glitchtip.com/documentation](https://glitchtip.com/documentation).
- **Project DSN:** stored in ENAC-IT's Infisical vault, never in the
  repo. Where and how to get access: [Tools and access](../infra/05-tools-and-access.md).

## How errors reach GlitchTip

There is no Sentry SDK. `src/utils/glitchtip.ts` is a ~2 KB
dependency-free reporter that speaks the GlitchTip envelope protocol
([plan 1569](../implementation-plans/frontend-glitchtip-error-reporting.md)).
`src/boot/sentry.ts` wires it in. Capture paths:

- Vue component errors via `app.config.errorHandler`, with
  `componentName`, `lifecycleHook` and shallow `propsData` attached.
- Router errors, `window` `error` and `unhandledrejection` listeners.
- HTTP 5xx responses from the ky client in `src/api/http.ts`.

Chunk-load failures and other noise are filtered through `ignoreErrors`.
Each event carries breadcrumbs (fetch, console, clicks, navigation) and
`contexts.trace.trace_id`, one id per navigation. The same id goes out as
a W3C `traceparent` header on every `/api` request
([plan 2372](../implementation-plans/2372-traceparent-propagation.md)),
which is meant to make the event searchable in Tempo; see
[Debugging with traces](../infra/06-debugging-with-traces.md) for the
current verification status. No performance or span events are sent:
GlitchTip's Performance tab stays empty by design.

## Configuring a deployment

Two env vars drive it, resolved at runtime in
[`src/config/runtime.ts`](https://github.com/epfl-enac/co2-calculator/blob/main/frontend/src/config/runtime.ts):

| Variable          | Purpose                                             |
| ----------------- | --------------------------------------------------- |
| `APP_SENTRY_DSN`  | Project DSN. Empty/unset → Sentry init skipped.     |
| `APP_ENVIRONMENT` | Event label (`development`, `stage`, `production`). |

> **⚠️ Empty DSN disables reporting.** `helm/values.yaml` ships
> `APP_SENTRY_DSN: ""`; the real DSN is set per cluster in the ops
> repo (`enack8s-app-config` / `openshift-app-config`), not here.

Set them per context:

- **Production/stage:** pod env via Helm `frontend.env`, overridden
  in the ops repo. The same bundle ships everywhere; values are
  injected at container startup, not baked in.
- **Local dev:** copy `frontend/.env.example` to `.env.local` and
  fill `APP_SENTRY_DSN`.
- **docker-compose:** export `APP_SENTRY_DSN` in your shell before
  `docker compose up`.

Under the pod's `readOnlyRootFilesystem`, these values are injected
at startup into `/tmp/injectEnv.js` and read from
`window.injectedEnvVariable` — see the
[implementation plan](../implementation-plans/344-frontend-error-monitoring.md)
for the runtime-injection design.

## Troubleshooting

- **No events in GlitchTip:** open the deployed app, load
  `/injectEnv.js` in the browser, and confirm `APP_SENTRY_DSN` is a
  non-empty value. Empty → ops repo override is missing.
- **Stack traces are minified:** known limitation. Source maps are
  disabled (`sourcemap: false`) to keep the bundle small; traces show
  line:column only. Reading minified frames is the current tradeoff.

**Next step:** to enable reporting on a new environment, request a
GlitchTip project from nicdub, then add the DSN to that cluster's
ops-repo values — do not commit it here.
