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
- **Project DSN:** stored in
  [Infisical](https://enac-it-secrets.epfl.ch/project/17dcca22-b05d-4d28-b7aa-c2770018f5be/secrets/overview?secretPath=%2Fepfl-enac%2Fglitchtip),
  never in the repo.

## How errors reach GlitchTip

`@sentry/vue` is lazy-loaded so the ~900 KiB SDK stays off the
critical path. Four capture paths feed it:

- Vue lifecycle/render errors via `app.config.errorHandler`.
- Synchronous browser errors via the `window` `error` listener.
- Unhandled promise rejections via the `unhandledrejection` listener.
- HTTP 5xx responses via `captureMessage` in
  [`src/api/http.ts:190`](https://github.com/epfl-enac/co2-calculator/blob/main/frontend/src/api/http.ts).

Noise (ResizeObserver loops, aborted fetches) is filtered. See
[`src/boot/sentry.ts`](https://github.com/epfl-enac/co2-calculator/blob/main/frontend/src/boot/sentry.ts)
for the full list and the `tracesSampleRate: 0.05` setting.

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
