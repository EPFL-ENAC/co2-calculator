---
status: delivered
issue: 860
last_updated: 2026-05-29
title: "Dev docs SSoT audit"
summary: "Page-per-page review of dev docs: duplicate clusters with SSoT winners, stale-fact findings against the codebase, the three highest-confidence fixes, plus the follow-up checklist now executed in this PR."
---

# 860 — Dev docs SSoT audit

This PR began as a **read-only audit** of `docs/src/` plus three
top-level contributor files (`README.md`, `CONTRIBUTING.md`,
`frontend/README.md`, `backend/...`). It surfaces duplicate clusters,
identifies a Single Source of Truth (SSoT) winner per cluster, and lists
stale facts that contradict the codebase. **Three high-confidence
fixes** shipped first; a **follow-up pass then executed the action
checklist** below (see the checked items and the `docs(860):` commits on
this branch).

This audit is a follow-up pass on issue #860; the broader refresh batch
is captured in
[`860-dev-docs-refresh.md`](860-dev-docs-refresh.md). Auth-flow docs
were SSoT-consolidated on `dev` in `06dcf902` / `0b7a4ad6` and are
**out of scope** here.

## Duplicate clusters

Ordered HIGH → LOW. Each row gives the cluster, the proposed SSoT
winner, and the recommended action. The actions called out below were
executed in this PR's follow-up pass — see the
[Action checklist](#action-checklist-executed-in-this-prs-follow-up-pass).

### HIGH — Backend install / setup

- Files: `README.md` (root), `CONTRIBUTING.md`, `docs/src/backend/01-overview.md`, `docs/src/backend/04-README.md`.
- Overlap: prerequisites, `make install`, `make docker-up`, env setup,
  `.env.example`, run commands.
- SSoT winner: `docs/src/backend/01-overview.md` — most complete, lives
  next to architecture pages.
- Action: shrink `04-README.md` to a 10-line pointer (or delete it and
  redirect cross-links). Root `README.md` keeps the quick-start it
  already has; `CONTRIBUTING.md` already cross-links correctly.

### MODERATE — Tech stack

- Files: `README.md` (Tech Stack mini-section), `docs/src/architecture/08-tech-stack.md`, ADRs `002-frontend-framework.md`, `003-backend-framework.md`.
- SSoT winner: `architecture/08-tech-stack.md` — current, dated
  `2025-12-11`, broad coverage.
- Action: leave ADRs untouched (decision records, immutable rationale).
  Root `README.md` already defers — keep it that way.

### MODERATE — Contributing / standards

- Files: `CONTRIBUTING.md` (root), `docs/src/architecture/documentation-standards.md`, `docs/src/architecture/code-standards.md`.
- SSoT winner: `CONTRIBUTING.md` for the onboarding flow; the two
  `architecture/*` pages own the actual rule text.
- Action: keep the current split. `CONTRIBUTING.md` already links to
  both. Verify each rule lives in exactly one place during follow-up;
  no edits in this PR.
- Note: `CLAUDE.md` (root) contains only RTK tooling notes, not project
  standards — not part of this cluster.

### MODERATE — Background processing

- Files: `docs/src/backend/01-overview.md` (Celery + Redis section), ADRs `010-background-job-processing.md`, `016-pipeline-two-path-principle.md`, plan `310-overview.md`.
- SSoT winner: ADR-010 (decision) + ADR-016 (path principle).
- Action: rewrite the background-processing section of `01-overview.md`
  to point at ADR-010 / ADR-016. **Done in this PR** (first pass plus the
  follow-up trim; see Stale-fact fixes below).

### LOW — Permissions

- Files: `docs/src/backend/06-PERMISSION-SYSTEM.md` (overview),
  `docs/src/backend/permissions/` (subsection).
- Already well-split (overview + detail). **No action.**

### SKIP — Auth flow

- Recently consolidated to SSoT (`docs/src/architecture/04-auth-flow.md`).
  **Do not touch.**

## Stale-fact findings

Ordered HIGH → LOW. All findings below are now applied — the three
"(fixed in this PR)" items in the first pass, the rest in the follow-up
pass on this branch.

### HIGH — Python version drift (fixed in this PR)

- Files: `docs/src/backend/01-overview.md:54`, `docs/src/backend/04-README.md:8`.
- Claim: "Python 3.11+".
- Evidence: root `.python-version` pins `3.12.7`; root `README.md`
  lists Python 3.12+; `architecture/08-tech-stack.md` lists Python
  3.12; backend Docker image is `python3.12-alpine`.
- Fix: 3.11+ → 3.12+.

### HIGH — Frontend dev workflow drift (fixed in this PR)

- File: `frontend/README.md` (whole file).
- Claim: `yarn` / `npm install`, `quasar dev`, `quasar build`.
- Evidence: repo is npm-only (`package-lock.json`, `frontend/Makefile`'s
  `install` runs `npm install`). Project convention is `make dev` /
  `make localbuild` (see `frontend/Makefile`); root `README.md` and
  `CONTRIBUTING.md` both use `cd frontend && make dev`.
- Fix: rewrite the dev/install/build snippets to use the `make` targets
  the rest of the repo standardizes on.

### HIGH — Backend Celery / Redis claims (fixed in this PR)

- File: `docs/src/backend/01-overview.md` (lines ~6, 144, 154-165, 199-203, 243, 264, 269-272).
- Claim: Celery handles background tasks; Redis is the broker;
  `make celery-worker` / `make celery-beat` / `make celery-flower`
  exist; `redis-cli LLEN celery` for debugging.
- Evidence: `backend/pyproject.toml` has no Celery dependency;
  `backend/Makefile` has no celery / redis targets; `backend/app/`
  contains no Celery imports; no `REDIS_URL` in `.env.example` or app
  config. ADR-010 records that Celery + Redis was **deferred**: jobs
  run via in-process `asyncio.create_task` with a 10-second safety-net
  poller (see also ADR-016 for the two-path principle).
- Fix: replace Celery/Redis content in `01-overview.md` with a short
  pointer to ADR-010 / ADR-016. The fake `make celery-*` and
  `redis-cli` commands are removed — they were actively misleading.

### MODERATE — Env URLs in root `README.md` (fixed in follow-up pass)

- File: `README.md` (top of file).
- Claim: dev / stage / pre-prod URLs are hardcoded inline.
- Issue: no SSoT link; the same URLs are repeated in
  `architecture/05-environments.md`.
- Fix: `README.md` now links to `architecture/05-environments.md`, which
  gained a `URL` column and is the one place these URLs are maintained.

### MODERATE — Stale Redis/Celery in `05-environments.md` (fixed in follow-up pass)

- File: `docs/src/architecture/05-environments.md`.
- Claim: a "Redis/Celery Configuration" table (workers / Redis mode /
  task retention per env) and a required `REDIS_URL` env var.
- Evidence: same as the backend Celery finding above — no Celery/Redis
  in `backend/pyproject.toml`, `Makefile`, `.env.example`, or app code;
  jobs run in-process per ADR-010. (Two `auth.py` comments mention a
  _future_ Redis-backed rate limiter — not current infra.)
- Fix: removed the table and the `REDIS_URL` row; replaced with a
  one-line accurate note pointing to ADR-010. (Discovered while wiring
  up the env-URL SSoT; not in the original cluster list.)

### LOW — Backend `01-overview.md` env table (fixed in follow-up pass)

- File: `docs/src/backend/01-overview.md` Configuration section.
- Notes: mentioned `OIDC_*` / `OAUTH_*` env names with no link to the
  auth SSoT.
- Fix: added a cross-link to `architecture/04-auth-flow.md` next to the
  OAuth/OIDC block; the env list stays for local setup. (Auth-flow SSoT
  has since stabilized on `dev`, so the earlier freeze no longer
  blocks a one-way link.)

## Action checklist (executed in this PR's follow-up pass)

- [x] Shrink `docs/src/backend/04-README.md` to a pointer page (kept as
      a pointer; dropped its `Quick Start` nav + `.pages` entries).
- [x] Rewrite the "Background Processing" section of `01-overview.md` as
      a pure pointer to ADR-010 / ADR-016 (dropped the residual
      "no Celery/Redis" framing).
- [x] Replace inline env URLs in root `README.md` with a link to
      `architecture/05-environments.md` (which is now the URL SSoT).
- [x] Sweep `01-overview.md` for the auth-flow SSoT link — added a
      cross-link from the OAuth/OIDC env block to `04-auth-flow.md`.
- [x] Audit `docs/src/frontend/` for `quasar` command leftovers — none
      found. The remaining `quasar` references are legitimate framework
      docs (SCSS bridge, `quasar.config.js`, design-token integration);
      the stale CLI commands were already removed from `frontend/README.md`
      in the first pass.

### New follow-up surfaced (not in this PR)

- [ ] Align the Quick Start in `docs/src/frontend/01-overview.md` with
      the repo's `make` convention — it still uses raw `npm install` /
      `npm run dev` / `npm run build`, whereas root `README.md`,
      `CONTRIBUTING.md`, and `frontend/README.md` standardize on
      `cd frontend && make dev`. Adjacent to the frontend-workflow drift
      finding above; left out here to keep this pass scoped.

## Out of scope for this PR

- Sweeping rewrites of duplicate files.
- Deleting any duplicate page.
- Touching `docs/src/architecture/04-auth-flow.md` or any auth-flow
  content.
- Rewriting `architecture/08-tech-stack.md`.

## References

- [ADR-010 — Background Job Processing](../architecture-decision-records/010-background-job-processing.md)
- [ADR-016 — Two-Path Pipeline Principle](../architecture-decision-records/016-pipeline-two-path-principle.md)
- [Documentation Standards](../architecture/documentation-standards.md) — the 10-Minute Rule this audit follows.
- Commits `06dcf902`, `0b7a4ad6` — recent auth-flow SSoT consolidation (out of scope).
