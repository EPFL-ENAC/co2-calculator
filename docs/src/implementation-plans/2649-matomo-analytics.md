---
status: in-progress
issue: 2649
last_updated: 2026-09-03
title: "Frontend usage analytics — self-hosted Matomo (ENAC web analytics)"
summary: "Adds cookieless Matomo page-view tracking to the Quasar SPA, gated on a per-instance site id. Config follows the existing runtime-injection chain (.env.example → quasar.config.js → runtime.ts → entrypoint.sh → Helm), with APP_MATOMO_URL defaulting to https://enac-webanalytics.epfl.ch/piwik/ and APP_MATOMO_SITE_ID unset by default so dev/CI/unconfigured deploys stay silent. Tracked URLs are normalized to route patterns so unit acronyms never leave the app."
---

# Frontend usage analytics — self-hosted Matomo

## 1. Problem

Issue #2649: we have no usage data — which modules are opened, which pages are
abandoned, whether the back-office is used at all. We want the ENAC IT4R
self-hosted, open-source option (Matomo at `https://enac-webanalytics.epfl.ch/piwik/`),
not a third-party SaaS.

The app ships **one Vite bundle to dev/stage/prod** (`docker/entrypoint.sh` →
`/injectEnv.js` → `window.injectedEnvVariable`), so the Matomo endpoint and the
site id cannot be baked at build time. They must ride the existing runtime
config chain, exactly like `APP_SENTRY_DSN`.

## 2. Configuration design

Two new `APP_*` variables, resolved in `src/config/runtime.ts` with the same
`injected || import.meta.env || default` cascade as every other value there:

| Variable             | Default                                    | Behaviour                                                                    |
| -------------------- | ------------------------------------------ | ---------------------------------------------------------------------------- |
| `APP_MATOMO_URL`     | `https://enac-webanalytics.epfl.ch/piwik/` | Code default (like `APP_MAP_TILE_STYLE_URL`). Trailing slash normalized.     |
| `APP_MATOMO_SITE_ID` | _(unset)_                                  | **The on/off switch.** Empty → no script loaded, no requests (like the DSN). |

**One Matomo site per instance** (dev / stage / prod each get their own site id
from the ENAC analytics admin), rather than one site plus an environment
dimension. Reasons: dev traffic never pollutes prod numbers, retention and
access can differ per site, and turning an instance off is "unset the id".
`runtimeConfig.environment` is still sent as a custom dimension so a
misconfigured pod is visible in the data rather than silent.

Wiring, mirroring the Sentry chain end to end:

| File                                       | Change                                                                     |
| ------------------------------------------ | -------------------------------------------------------------------------- |
| `frontend/.env.example`                    | Both vars, documented, `APP_MATOMO_SITE_ID=` empty → local dev is silent.  |
| `frontend/quasar.config.js`                | `build.env`: `APP_MATOMO_URL`, `APP_MATOMO_SITE_ID` from `process.env`.    |
| `frontend/src/env.d.ts`                    | Two `readonly` entries on `ImportMetaEnv`.                                 |
| `frontend/src/config/runtime.ts`           | `matomoUrl` (with default) and `matomoSiteId` (no default).                |
| `helm/values.yaml`                         | `frontend.env` placeholders + comment that ops repo sets the real site id. |
| `docs/src/architecture/05-environments.md` | Both rows in the frontend env table.                                       |
| `docker/entrypoint.sh`                     | **No change** — it forwards every `APP_*` var generically.                 |

Per-environment values are set in the ops repo (`enack8s-app-config` /
`openshift-app-config`), same as the Sentry DSN — no rebuild to enable or
disable analytics on an instance.

## 3. Tracking client

**New — `frontend/src/utils/matomo.ts`** (~80 lines, no npm dependency):

- `initMatomo({ url, siteId, environment })` — no-ops without a site id;
  otherwise seeds `window._paq`, applies the privacy config below, and injects
  `<script async src="${url}matomo.js">`. Loading Matomo's own `matomo.js` from
  the configured host (rather than hand-rolling a beacon, as we did for
  GlitchTip) is deliberate: the tracker is versioned _with the server we point
  at_, and opt-out / DoNotTrack / heartbeat / link tracking come for free. It is
  a runtime script from a configured host, not a new package — no dependency
  decision to defer to the lead.
- `trackPageView({ url, title, referrer })` — pushes onto `_paq`; safe before
  the script loads (that is what the array queue is for). Custom URL _and_
  referrer are absolute: Matomo resolves a relative URL against the tracker's
  own host, which would attribute every intra-SPA navigation to the analytics
  server. The injected `<script>` carries `referrerPolicy="no-referrer"` so the
  tracker host never sees an SPA path in the `Referer` header.
- `buildTrackedUrl(route)` — the normalization described in §4. Pure function,
  unit-tested.

**New — `frontend/src/boot/matomo.ts`**, added to the boot array in
`quasar.config.js` after `sentry`:

- Calls `initMatomo(runtimeConfig)`.
- `router.afterEach` → `setReferrerUrl` / `setCustomUrl` / `setDocumentTitle` /
  `trackPageView`, the standard Matomo SPA sequence.
- Skips entirely when `window.__LIGHTHOUSE_BYPASS__` is set, so Lighthouse CI
  runs don't inflate the numbers.
- Errors stay with GlitchTip — nothing about error reporting changes.

## 4. Privacy posture

Non-negotiables baked into `initMatomo`, not left to server config:

- **`disableCookies()`** — cookieless tracking, so no consent banner and no new
  i18n strings. Trade-off: unique-visitor counts become approximate; page-view
  and module-usage trends, which is what #2649 asks for, are unaffected.
- **No `setUserId`, no sciper, no email.** Nothing that identifies a person.
- **URL normalization.** Our paths carry the org unit:
  `/en/ENAC-IT4R/2024/results`. A small unit plus a timestamp is close to
  identifying, so every param outside the language/year/module allow-list is
  replaced by `_` — `/en/_/2024/results` — while language, year and module stay
  (they are the interesting dimensions). Query strings are dropped wholesale
  rather than allow-listed, so a token or filter value can never leak.

  Masking is **positional**: each path segment is judged by the matched route
  pattern above it, never by comparing it against param values. Value
  comparison would over-mask (a plan id of `2024` blanks the year segment) and,
  worse, under-mask — `route.path` keeps percent-encoding while `route.params`
  is decoded, so a unit needing encoding would sail through unmasked. Splitting
  the pattern is depth-aware because an inline regex can contain a slash
  (`:unit([^/]+)`). A segment with no pattern above it (the not-found catch-all)
  is masked: the failure direction is losing a dimension, never leaking an id.

- `setDocumentTitle` uses the route name, not the rendered title, for the same
  reason (rendered titles can contain unit names).
- Data stays on EPFL infrastructure; nothing goes to a third party.

If the unit dimension turns out to be needed for a real question later, it is a
separate, explicit change (a custom dimension with a documented rationale) —
not something we enable by default here.

## 5. CSP

`frontend/nginx.conf` sets no `Content-Security-Policy` today, so nothing
blocks this. Noted here because the security-in-depth work (#89) will add one:
it must then allow the Matomo host in `script-src`, `img-src` and `connect-src`,
and the host must come from the same env var rather than being hardcoded.

## 6. Tests

The DOM-touching part of `initMatomo` is three lines (create script, set src,
append); everything worth asserting is a pure function, so both specs run in the
Playwright CT runner's Node process with no browser harness:

- `frontend/tests/unit/matomo-url.spec.ts` — `buildTrackedUrl` masks the unit,
  masks record ids, masks a param added later (allow-list, not deny-list), keeps
  language/year/module, drops query strings, handles print routes; and
  `buildTrackedTitle` falls back to the _masked_ URL, never the raw path.
- `frontend/tests/unit/matomo-init.spec.ts` — no site id → `isTrackingEnabled`
  false and `matomoInitCommands` empty (so no script is injected); with a site id
  → `disableCookies` queued first, tracker URL and site id set, environment
  dimension sent, `setUserId` never queued, and `trackerScriptSrc` normalizing an
  endpoint with or without a trailing slash.
- No e2e: integration runs have no site id, so tracking is off by construction —
  which is what the init spec asserts.

## 7. Rollout

1. Request three site ids from the ENAC web analytics admins (dev / stage / prod).
2. Merge with all instances unset → zero behaviour change, verifiable in prod.
3. Set the dev site id in the ops repo, confirm hits land and that no unit
   acronym appears in any tracked URL.
4. Stage, then prod.

## 8. Open questions

- Should the print routes (`/results/print`, `/simulation/explore/print`) be
  tracked? They are user-initiated today, so the plan tracks them; excluding
  them is a one-line change if the numbers look inflated.
- Retention on the Matomo side — ENAC default, or a shorter window? Ops call.
