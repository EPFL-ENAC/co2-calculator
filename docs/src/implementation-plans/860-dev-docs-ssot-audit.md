---
status: delivered
issue: 860
last_updated: 2026-05-28
title: "Dev docs SSoT audit"
summary: "Page-per-page review of dev docs: duplicate clusters with SSoT winners, stale-fact findings against the codebase, and the three highest-confidence fixes shipped in this PR."
---

# 860 — Dev docs SSoT audit

This PR is a **read-only audit** of `docs/src/` plus three top-level
contributor files (`README.md`, `CONTRIBUTING.md`, `frontend/README.md`,
`backend/...`). It surfaces duplicate clusters, identifies a Single
Source of Truth (SSoT) winner per cluster, and lists stale facts that
contradict the codebase. **Three high-confidence fixes** ship with this
PR; the rest is a checklist for follow-up.

This audit is a follow-up pass on issue #860; the broader refresh batch
is captured in
[`860-dev-docs-refresh.md`](860-dev-docs-refresh.md). Auth-flow docs
were SSoT-consolidated on `dev` in `06dcf902` / `0b7a4ad6` and are
**out of scope** here.

## Duplicate clusters

Ordered HIGH → LOW. Each row gives the cluster, the proposed SSoT
winner, and the recommended action. None of these are executed in this
PR beyond the targeted fixes below.

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
  to point at ADR-010 / ADR-016. **Partially done in this PR** (see
  Stale-fact fixes below).

### LOW — Permissions

- Files: `docs/src/backend/06-PERMISSION-SYSTEM.md` (overview),
  `docs/src/backend/permissions/` (subsection).
- Already well-split (overview + detail). **No action.**

### SKIP — Auth flow

- Recently consolidated to SSoT (`docs/src/architecture/04-auth-flow.md`).
  **Do not touch.**

## Stale-fact findings

Ordered HIGH → LOW. "Fixed in this PR" = applied; the rest are queued
for follow-up.

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

### MODERATE — Env URLs in root `README.md` (not fixed)

- File: `README.md` (top of file).
- Claim: dev / stage / pre-prod URLs are hardcoded inline.
- Issue: no SSoT link; the same URLs are repeated in
  `architecture/05-environments.md`.
- Suggested fix (follow-up): link to `05-environments.md` from
  `README.md` instead of restating; keep `05-environments.md` as the
  one place URLs are maintained.

### LOW — Backend `01-overview.md` env table

- File: `docs/src/backend/01-overview.md` Configuration section.
- Notes: mentions `OIDC_*` / `OAUTH_*` env names — once SSoT moves to
  `04-auth-flow.md`, link there instead of repeating env-var lists.
  Out of scope (auth-flow SSoT freeze).

## Action checklist (follow-up PRs)

- [ ] Shrink `docs/src/backend/04-README.md` to a pointer page (or
      delete + redirect).
- [ ] Rewrite the "Background Processing" section of
      `01-overview.md` as a pure pointer to ADR-010 / ADR-016 once
      readers stop expecting Celery content.
- [ ] Replace inline env URLs in root `README.md` with a link to
      `architecture/05-environments.md`.
- [ ] Sweep `01-overview.md` once auth-flow SSoT links stabilize.
- [ ] Audit `docs/src/frontend/` for `quasar` command leftovers after
      this PR lands.

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
