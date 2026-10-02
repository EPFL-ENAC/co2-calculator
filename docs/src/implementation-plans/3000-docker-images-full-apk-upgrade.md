---
status: delivered
issue: 3000
last_updated: 2026-10-02
summary: Trivy blocked the dev deploy on HIGH CVEs — pcre2 10.48 in the nginx-alpine docs/frontend images, urllib3 2.7.0 in the backend venv; the three runtime stages now run a plain `apk upgrade --no-cache` instead of naming one package per CVE, and uv.lock bumps urllib3 to 2.8.0
---

# 3000 — full `apk upgrade` in the runtime images, urllib3 2.8.0

## Problem

The dev pipeline (gitlab.epfl.ch build-push-deploy) fails its Trivy scan
(`HIGH,CRITICAL`, fixed only), so nothing deploys. On `dev` @ `ff0418f51`, a
local `docker build --pull` + `trivy image` reproduces it:

| Image    | Package                        | Installed → fixed   | CVE                    |
| -------- | ------------------------------ | ------------------- | ---------------------- |
| docs     | `pcre2` (alpine 3.24.2)        | 10.48-r0 → 10.49-r0 | CVE-2026-103111        |
| frontend | `pcre2` (alpine 3.24.2)        | 10.48-r0 → 10.49-r0 | CVE-2026-103111        |
| backend  | `urllib3` (python, transitive) | 2.7.0 → 2.8.0       | CVE-2026-97687, -97689 |

This was the third round of hand-naming Alpine packages in the Dockerfiles
(openssl CVE-2026-14456, then libuuid, now pcre2). Each round lands after the
deploy is already blocked.

## Decision (maintainer, 2026-10-02)

The project is in maintenance mode. Every runtime stage runs a plain
`apk upgrade --no-cache`, so each rebuild takes whatever Alpine has fixed.
That trades per-CVE traceability in the Dockerfile for zero upkeep. The scan
now fails only on CVEs Alpine itself hasn't fixed, which no Dockerfile line
could fix anyway. Within a stable Alpine branch (3.24) the repo carries
security and bug fixes only, so a blanket upgrade is low-risk.

Rejected: keep naming packages (add `pcre2`), which was the old pattern and
needs a PR per CVE.

## What shipped

- `docs/Dockerfile`, `frontend/Dockerfile` (nginx-unprivileged alpine):
  `apk upgrade --no-cache libcrypto3 libssl3` → `apk upgrade --no-cache`.
  The named openssl upgrade was already a no-op: the base now ships
  3.5.8-r0.
- `backend/Dockerfile` (python alpine): `apk upgrade --no-cache libcrypto3
libssl3 libuuid` → `apk upgrade --no-cache`. The base still lagged on
  openssl (3.5.7) and libuuid (2.42.1); the full upgrade covers both and
  pulls openssl 3.5.9.
- `backend/uv.lock`: `uv lock --upgrade-package urllib3` (2.7.0 → 2.8.0,
  nothing else moves). It is transitive, via botocore, elastic-transport,
  requests and sentry-sdk, so `pyproject.toml` is unchanged.

Out of scope: `frontend/Dockerfile.storybook` is built by a GitHub workflow,
not the GitLab dev pipeline.

## Verification

- Trivy (`--severity HIGH,CRITICAL`) on the three rebuilt images: 0 / 0 / 0.
- docs and frontend containers serve `/` (and frontend `/ready`) with 200;
  `pcre2-10.49-r0` installed.
- Backend image imports `app.main` with urllib3 2.8.0 and OpenSSL 3.5.9.
- Full backend suite on urllib3 2.8.0: 3640 passed, 1 skipped, 0 failed.

Images reused by the pipeline (`reuse_unchanged_images`) are not rebuilt,
so a CVE fixed upstream after a context's last change still needs a rebuild
to land. The scheduled registry scan surfaces those.
