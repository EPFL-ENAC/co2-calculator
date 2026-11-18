---
status: delivered
issue: 3185
last_updated: 2026-11-10
summary: "Remediate the security audit job-d0adab0d: object-level authorization and dependencies first, then boot, session and policy hardening, CSV neutralization, CI hygiene and temporary-upload scoping."
---

# Security audit job-d0adab0d: remediation

The audit ran on `main` at 1.4.21. Each phase is a small change with regression
tests. The rest of the code-scanning work is in
[3185-code-scanning-sweep](./3185-code-scanning-sweep.md).

## Status

| Phase | Work                                           | State                      |
| ----- | ---------------------------------------------- | -------------------------- |
| 1     | Object-level authorization                     | Released in 1.4.22 (#3186) |
| 2     | Vulnerable and unused dependencies             | Released in 1.4.22 (#3187) |
| 3     | Boot guard, logout cookie, policy default-deny | On dev (#3217)             |
| 4     | CSV formula neutralization                     | On dev (#3217)             |
| 5     | CI, container and config hygiene               | On dev (#3217)             |
| 6     | Temporary upload scoping                       | On dev (#3217)             |

Outside this repository, `enacit4r-files` got an `immutable-tags` ruleset and a
clean lockfile (its #35).

## Phase 3

- `assert_security_settings` refuses signing keys that start with `change-me` or
  are under 32 characters. It still runs in the lifespan and skips local.
- Logout clears the session cookie with the `SameSite` and `Secure` attributes
  it was issued with.
- `query_policy` raises on an unknown name. The one caller reaching the old
  allow fallback was `unit:query`, a no-op because the query is already bounded
  by the user's membership rows, so that call is gone.

## Phase 4

- `SafeCsvWriter` (`app/utils/csv_safe.py`) neutralizes every cell, so an export
  can't forget. Four exports were unprotected, not the three the audit named. A
  guard test fails on any bare `csv.writer` in `app/api/v1/`.
- `escapeCsvValue` neutralizes formula prefixes too, but leaves plain numbers
  alone so negative values stay numeric. It moved to `results-csv.ts`, because
  `download.ts` imports the i18n boot file and a unit test can't load that.

## Phase 5

- The Storybook image uses the unprivileged nginx base.
- `deploy-storybook.yml` sent the undefined `secrets.token`, so every dispatch
  got a 401 that `curl` hid, and the manifests have not moved since 2026-01. It
  now uses `CD_TOKEN` and `curl -fsS`, so a refused dispatch fails the job.
- All 55 action references are pinned to commit SHAs, and Dependabot's new
  `github-actions` entry keeps them current.
- Every image declares `ARG GIT_SHA` above its `apk upgrade`, so each commit
  re-runs it. A cached layer kept musl 1.2.6-r2 in the frontend and docs
  images, and Trivy blocked the first dev deploy of #3217.
- The `locahost` default is fixed. The CA default keeps its name because the helm
  chart mounts the certificate under that filename.

## Phase 6

- Uploads go to `tmp/<user id>/<timestamp>/`.
- `POST /sync/dispatch` and `DELETE /files/...` refuse a path outside the
  caller's folder. The check normalizes the path first.
- An upload in flight during the deploy has to be uploaded again.

## Before deploying

- Confirm `JWT_HMAC_KEY` and `SESSION_HMAC_KEY` are at least 32 characters on
  dev, stage and prod. A shorter key stops the backend booting.
- Confirm `CD_TOKEN` can dispatch to `EPFL-ENAC/enack8s-app-config`. If it can't,
  `deploy-storybook` turns red. If it can, Storybook deploys for the first time
  since 2026-01, on the new image.

## Won't do

- **SSRF private-IP and DNS-rebinding checks.** The guard is an https-only,
  fail-closed host allowlist, and connector hosts inside EPFL can legitimately
  resolve to private IPs.
- **Helm `runAsNonRoot`, `runAsUser` and `fsGroup`.** The OpenShift restricted SCC
  enforces non-root and assigns the UID, so pinned UIDs would conflict.
- **GitLeaks hits.** False positives: emission-factor key names.
- **`__LIGHTHOUSE_BYPASS__`.** It only skips client route guards, and the backend
  authorizes every call.

## Left for later

The rescans (job-0631fe40, job-945ed7b9) reported no CSP, HSTS,
X-Frame-Options or Referrer-Policy headers. The load balancer already sends
HSTS. `frontend/nginx.conf` now sends X-Frame-Options, X-Content-Type-Options,
Referrer-Policy and a CSP limited to `frame-ancestors`, `base-uri` and
`object-src`, with `add_header_inherit merge` (nginx 1.29.3+) so the locations
that add their own headers keep them.

Still open: a `script-src` CSP. It has to allow the font host, the map tile
hosts, the analytics host and the GlitchTip host, which differs per
environment, so it needs its own tested change.
