---
status: delivered
issue: 1704
last_updated: 2026-08-18
title: "Rename SECRET_KEY to JWT_HMAC_KEY, split out SESSION_HMAC_KEY, prune dead env vars"
summary: "SECRET_KEY renamed to JWT_HMAC_KEY (JWT signing only); Starlette SessionMiddleware's reused key split into a new dedicated SESSION_HMAC_KEY so rotating one signing domain never invalidates the other. Removed dead OPA_URL/OPA_TIMEOUT/OPA_ENABLED (never read — ADR-005 rejected real OPA). backend/.env.example now round-trips 1:1 with config.py in both directions."
---

# 1704 — Rename SECRET_KEY → JWT_HMAC_KEY

## 1. Problem

Three asks:

1. Rename `SECRET_KEY` to `JWT_HMAC_KEY` (name no longer says what the key is for).
2. Verify the key isn't reused as a salt/key for S3 or anything else; add a
   dedicated var if it is.
3. Find dead env vars (`OPA_URL`?, Loki?) and reconcile `config.py` ↔
   `.env.example` in both directions.

## 2. Findings

**Reuse audit (#2).** `SECRET_KEY` was never used as an S3 or KDF salt —
`FILES_ENCRYPTION_KEY/SALT`, `CREDENTIALS_ENCRYPTION_KEY/SALT`, and
`S3_SECRET_ACCESS_KEY` are already fully separate, dedicated vars. It _was_
reused for two different HMAC-signing purposes, though: JWT signing
(`app/core/security.py`) and Starlette `SessionMiddleware`'s cookie signing
(`app/main.py`, a 60s-lived cookie used only mid-OAuth-flow). Renaming the
var to `JWT_HMAC_KEY` while `SessionMiddleware` kept using it would make that
second use actively misleading, so it now gets its own `SESSION_HMAC_KEY` —
rotating the JWT signing key no longer needs to invalidate the OAuth-flow
session cookie's signing key, or vice versa.

**Dead vars (#3).** `OPA_URL` / `OPA_TIMEOUT` / `OPA_ENABLED` were never read
anywhere outside their own `Field()` declaration — ADR-005 rejected real OPA
in favor of in-code RBAC (`app/core/policy.py`'s `_evaluate_permission_policy`
does pure in-process Python; "OPA" in that module's docstrings is leftover
naming, not a live integration). Deleted.

Loki (`LOKI_*`) _is_ live — wired into `app/main.py` and `app/core/logging.py`
— just optional and not enabled in this repo's Helm values. Left as-is.

**`.env.example` reconciliation.** `comm`-diffed the two files' variable
names after the rename/OPA removal: 16 `config.py` fields had no
`.env.example` entry (`JWT_HMAC_KEY`, `SESSION_HMAC_KEY`, `OAUTH_ISSUER_URL`,
`HOST`, `PORT`, `WORKERS`, `GIT_SHA`, `DISPATCH_JOBS_INLINE`,
`RUN_DB_HEALTH_POLLER`, `RUN_PIPELINE_RECONCILER`, `RUN_POD_HEARTBEAT`,
`DB_HEALTH_CHECK_INTERVAL_SECONDS`, `DB_HEALTH_SLOW_THRESHOLD_MS`,
`PIPELINE_RECONCILER_INTERVAL_SECONDS`, `POD_HEARTBEAT_INTERVAL_SECONDS`,
`HOURS_PER_WEEK`, `WEEKS_PER_YEAR`); all now documented (commented where
they're infra/CI-set, e.g. `HOST`/`PORT`/`WORKERS` are normally uvicorn CLI
flags per `backend/Makefile`, not env vars, locally). No entries existed in
`.env.example` that were missing from `config.py`.

## 3. Deploy sequencing (Helm)

Every live K8s Secret (`existingSecret.enabled=true` path) currently has a
key literally named `SECRET_KEY`. The chart's `secretKeyRef` lookups now
default to `JWT_HMAC_KEY` / `SESSION_HMAC_KEY`, so an unmodified existing
Secret makes the backend/migration pods fail closed
(`CreateContainerConfigError`) on upgrade — by design, not a bug: no
dual-path env fallback was added (guardrails: no silent fallbacks, no
backward-compat paths).

**Before upgrading stage/prod**, operators must either:

- add `JWT_HMAC_KEY` and `SESSION_HMAC_KEY` entries to the existing Secret
  (reuse the current `SECRET_KEY` value for `JWT_HMAC_KEY` to keep existing
  `auth_token`/`refresh_token` cookies valid across the deploy; generate a
  fresh value for `SESSION_HMAC_KEY` — it's brand new), or
- temporarily override `backend.existingSecret.keys.jwtHmacKeyKey: SECRET_KEY`
  in values, then migrate the Secret at leisure.

The chart-managed-secret path (`existingSecret.enabled=false`, local/dev)
needs no manual step — `helm upgrade` recreates the Secret from
`backend.secrets.JWT_HMAC_KEY` / `.SESSION_HMAC_KEY`.

## 4. Files

- `backend/app/core/config.py` — `SECRET_KEY` → `JWT_HMAC_KEY` (default now
  `""`, mirroring `CREDENTIALS_ENCRYPTION_KEY`'s fail-closed shape instead of
  an insecure placeholder default); new `SESSION_HMAC_KEY`; `OPA_*` removed.
- `backend/app/main.py` — `SessionMiddleware(secret_key=...)` now reads
  `SESSION_HMAC_KEY`; `assert_security_settings` boot check extended to both
  new keys (fails closed outside `LOCAL_ENVIRONMENT` if either is unset).
- `backend/app/core/security.py`, `backend/app/api/v1/auth.py`,
  `backend/tests/integration/v1/test_auth_security.py` — `SECRET_KEY` →
  `JWT_HMAC_KEY`.
- `backend/.env.example`, `backend/.env` (local, gitignored) — key rename +
  full `config.py` reconciliation.
- `helm/values.yaml`, `helm/templates/backend-secret.yaml`,
  `helm/templates/_helpers.tpl`, `helm/templates/migration-job.yaml`,
  `helm/README.md` — key rename, new required `SESSION_HMAC_KEY` secret.
- `.github/workflows/publish_chart.yaml` — chart-render smoke test sets both
  new keys instead of the old one.
- Docs: `docs/src/architecture/04-auth-flow.md`,
  `docs/src/architecture/05-environments.md`,
  `docs/src/backend/01-overview.md`, `docs/src/infra/01-overview.md` (+
  deploy-sequencing note), and var-name mentions in the delivered 1552/458
  plans.

## 5. Verification

1. `uv run python -c "from app.core.config import get_settings; get_settings()"`
   — `JWT_HMAC_KEY`/`SESSION_HMAC_KEY` present, `SECRET_KEY`/`OPA_*` gone.
2. `make lint` — backend/frontend/docs prettier clean (pre-existing
   unrelated `1153-*.md` prettier warnings untouched by this branch).
3. `make type-check` — backend `ty`/ruff clean.
