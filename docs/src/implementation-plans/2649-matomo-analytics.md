---
status: in-progress
issue: 2649
last_updated: 2026-09-03
title: "Frontend usage analytics — self-hosted Matomo (ENAC web analytics)"
summary: "Adds cookieless Matomo page-view tracking to the Quasar SPA, gated on a per-instance site id (APP_MATOMO_SITE_ID, empty = off). The browser never calls Matomo directly: content blockers drop matomo.js/matomo.php by filename, so both the tracker and the hits go through a same-origin backend proxy at /api/v1/analytics, which is also the only place the upstream URL (MATOMO_URL) is configured. Tracked URLs mask unit acronyms and record ids positionally, and drop query strings."
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

One frontend variable and one backend variable:

| Variable             | Side     | Default                                    | Behaviour                                                                     |
| -------------------- | -------- | ------------------------------------------ | ----------------------------------------------------------------------------- |
| `APP_MATOMO_SITE_ID` | frontend | _(unset)_                                  | **The on/off switch.** Empty → no script loaded, no requests (like the DSN).  |
| `MATOMO_URL`         | backend  | `https://enac-webanalytics.epfl.ch/piwik/` | Upstream proxied by `/api/v1/analytics`. https only; a bad value 503s loudly. |

The site id is resolved in `src/config/runtime.ts` with the same
`injected || import.meta.env || default` cascade as every other value there.
The **upstream URL is backend config**: the browser never addresses Matomo
directly (§3b), so shipping the Matomo host to the client would be config
nobody reads — and the service location belongs on the side that is the source
of truth.

**One Matomo site per instance** (dev / stage / prod each get their own site id
from the ENAC analytics admin), rather than one site plus an environment
dimension. Reasons: dev traffic never pollutes prod numbers, retention and
access can differ per site, and turning an instance off is "unset the id".
`runtimeConfig.environment` is still sent as a custom dimension so a
misconfigured pod is visible in the data rather than silent.

Wiring, mirroring the Sentry chain end to end:

| File                                         | Change                                                                    |
| -------------------------------------------- | ------------------------------------------------------------------------- |
| `frontend/.env.example`                      | `APP_MATOMO_SITE_ID=` empty → local dev is silent.                        |
| `frontend/quasar.config.js`                  | `build.env`: `APP_MATOMO_SITE_ID` from `process.env`; boot slot `matomo`. |
| `frontend/src/env.d.ts`                      | One `readonly` entry on `ImportMetaEnv`.                                  |
| `frontend/src/config/runtime.ts`             | `matomoSiteId` (no default).                                              |
| `backend/.env.example`, `app/core/config.py` | `MATOMO_URL` setting, documented, https-only.                             |
| `helm/values.yaml`                           | `frontend.env` site id + `backend.env` `MATOMO_URL`.                      |
| `docker-compose.yml`                         | Site id on the frontend service; `MATOMO_URL` rides `backend/.env`.       |
| `docs/src/architecture/05-environments.md`   | Both rows in the env table.                                               |
| `docker/entrypoint.sh`                       | **No change** — it forwards every `APP_*` var generically.                |

Per-environment values are set in the ops repo (`enack8s-app-config` /
`openshift-app-config`), same as the Sentry DSN — no rebuild to enable or
disable analytics on an instance.

## 3. Tracking client

**New — `frontend/src/utils/matomo.ts`** (~80 lines, no npm dependency):

- `initMatomo({ siteId, environment })` — no-ops without a site id; otherwise
  seeds `window._paq`, applies the privacy config below, and injects
  `<script async src="/api/v1/analytics/js">`. Loading Matomo's own tracker
  (rather than hand-rolling a beacon, as we did for GlitchTip) is deliberate:
  it is versioned _with the server we point at_, and opt-out / DoNotTrack /
  heartbeat / link tracking come for free. It is a runtime script, not a new
  package — no dependency decision to defer to the lead.
- `trackPageView({ url, title, referrer })` — pushes onto `_paq`; safe before
  the script loads (that is what the array queue is for). Custom URL _and_
  referrer are absolute: Matomo resolves a relative URL against the tracker's
  own host, which would attribute every intra-SPA navigation to the analytics
  server. The injected `<script>` carries `referrerPolicy="no-referrer"`:
  same-origin now, but the tracker has no use for a `Referer` either way.
- `buildTrackedUrl(route)` — the normalization described in §4. Pure function,
  unit-tested.
- The proxy paths (`/api/v1/analytics/js`, `…/track`) are a constant here, not
  config: the browser has exactly one place to talk to. They deliberately
  mirror `API_BASE_URL` in `src/api/http.ts` without importing it — that module
  pulls in the ky client and i18n, which the tracker has no business loading.

**New — `frontend/src/boot/matomo.ts`**, added to the boot array in
`quasar.config.js` after `sentry`:

- Calls `initMatomo(runtimeConfig)`.
- `router.afterEach` → `setReferrerUrl` / `setCustomUrl` / `setDocumentTitle` /
  `trackPageView`, the standard Matomo SPA sequence.
- Skips entirely when `window.__LIGHTHOUSE_BYPASS__` is set, so Lighthouse CI
  runs don't inflate the numbers.
- Errors stay with GlitchTip — nothing about error reporting changes.

## 3b. Same-origin backend proxy

**Why.** Confirmed in the dev deployment: uBlock Origin blocks the tracker.
`matomo.js` and `matomo.php` are on the default EasyPrivacy/uBlock lists
matched **by filename on any host**, so self-hosting at EPFL earns no
exemption. The request is dropped client-side (`ERR_BLOCKED_BY_CLIENT`) while
the URL itself is perfectly valid. Nothing in our deployment was at fault —
there is no CSP in `nginx.conf`, the Helm ingress or `index.html`.

**What.** The backend serves both under neutral paths, Matomo's documented
proxy setup:

| Path                                | Upstream                  | Notes                                                                   |
| ----------------------------------- | ------------------------- | ----------------------------------------------------------------------- |
| `GET /api/v1/analytics/js`          | `${MATOMO_URL}matomo.js`  | Cached in-process for 1 h (changes only on a Matomo upgrade) + browser. |
| `GET\|POST /api/v1/analytics/track` | `${MATOMO_URL}matomo.php` | One hit forwarded per call.                                             |

- **New** — `backend/app/services/analytics_proxy_service.py` (outbound HTTP,
  script cache, header policy) and `backend/app/api/v1/analytics.py` (thin
  route: status translation only). No database, so no repo layer.
- **Public and out of the OpenAPI schema.** The tracker loads on the login page
  before any session exists, and nothing calls these through the ky client — a
  `<script>` tag and the tracker's own XHR do — so they would only be noise in
  the generated frontend types.
- **Forwarded:** `X-Forwarded-For` (the real client IP), `User-Agent`,
  `Accept-Language`, the query string and the POST body.
  **Never forwarded:** cookies and `Authorization` — our session cookie must
  not reach the analytics server. A hit carrying `token_auth` is refused with a
  400 rather than relayed: an authenticated write is not something the browser
  tracker needs, and this endpoint is unauthenticated. Bodies are capped at
  64 KB so the endpoint can't be used as a general-purpose relay.
- **Failure is loud**: unreachable upstream → 502, unusable `MATOMO_URL` → 503.
  Neither is visible to the user (a failed tracker load is silent in the
  browser), but both show up in logs and monitoring rather than as missing data.

**⚠️ Depends on Matomo trusting the header.** Matomo honours `X-Forwarded-For`
only when its own config lists it in `proxy_client_headers`. Without that, every
hit is attributed to the pod's egress IP — and since we track cookieless, where
the visitor id derives from IP + user agent, all visitors collapse into one.
Page-view counts stay right; visitor counts do not. **This must be confirmed
with the ENAC analytics admins when the site ids are requested.**

**Cost.** The frontend pod is no longer the only thing between the browser and
the tracker: analytics hits now consume a backend request each. They are small
and infrequent (one per navigation), and an upstream `httpx.AsyncClient` is
opened per hit — the same pattern as `taxonomy_cache_broadcast`. If volume ever
justifies it, a shared client is the first optimization.

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

`frontend/nginx.conf` sets no `Content-Security-Policy` today, so nothing blocks
this. Noted here because the security-in-depth work (#89) will add one: with the
proxy in place the tracker is same-origin, so `'self'` in `script-src`,
`img-src` and `connect-src` covers it — no Matomo host to allow-list. That is a
second, smaller reason to proxy.

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
  dimension sent, `setUserId` never queued, and both proxy paths same-origin and
  free of the `matomo.js`/`matomo.php` filenames that blockers match on.
- No e2e: integration runs have no site id, so tracking is off by construction —
  which is what the init spec asserts.

Backend — `backend/tests/unit/services/test_analytics_proxy_service.py`, driving
the service through an `httpx.MockTransport` (no new test dependency): the
tracker is fetched once and then served from cache; a hit carries the client IP,
user agent and language but never a cookie or `Authorization`; a POST body is
forwarded; `token_auth` is refused rather than relayed; an empty or non-https
`MATOMO_URL` raises rather than silently disabling tracking.

## 7. Rollout

1. Request three site ids from the ENAC web analytics admins (dev / stage / prod),
   **and confirm their Matomo trusts `X-Forwarded-For`** (`proxy_client_headers`)
   — without it the proxy attributes every hit to the pod's IP (§3b).
2. Merge with all instances unset → zero behaviour change, verifiable in prod.
3. Set the dev site id in the ops repo, confirm hits land and that no unit
   acronym appears in any tracked URL.
4. Stage, then prod.

## 8. Open questions

- Should the print routes (`/results/print`, `/simulation/explore/print`) be
  tracked? They are user-initiated today, so the plan tracks them; excluding
  them is a one-line change if the numbers look inflated.
- Retention on the Matomo side — ENAC default, or a shorter window? Ops call.
- The proxy recovers blocker-dropped hits, but nothing recovers a user who
  blocks the _inline_ queue too, or who has JS disabled. Expect the numbers to
  undercount somewhat; they are trend data, not attendance records.
