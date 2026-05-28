---
status: in-progress
last_updated: 2026-05-28
title: "Docs: single source of truth for auth flow"
summary: "Strip duplicated and stale auth narratives from backend and frontend overview docs. The architecture/04-auth-flow.md doc is the canonical source; everything else cross-links."
---

## Problem

Auth content currently spans 11 files in `docs/src/`. The canonical narrative lives at `docs/src/architecture/04-auth-flow.md` (delivered in PR #1313, kept current through PR #1314). Eight other files either repeat parts of the flow or reference endpoints that no longer exist post-PR #1314 (`/auth/me` was replaced by `GET /v1/session`; `auth_token` is set on the same-origin POST `/v1/session/exchange`, not on the OAuth callback redirect).

One file (`backend/01-overview.md`) contains an outright factual error: line 180 claims the frontend sends `Authorization: Bearer <token>`. The app uses `httpOnly` session cookies — never Bearer tokens. This contradicts ADR-012 and ADR-019.

## Principle

Auth is a **cross-domain architecture concern**. It belongs in `docs/src/architecture/`, not duplicated into the backend and frontend overview pages. Where auth must be referenced from non-architecture docs (e.g., a permissions doc explaining where the permission payload comes from), use a single-sentence cross-link and don't restate the flow.

## Scope

### A) Path-only fixes (mechanical, no narrative change)

Replace stale endpoint references with the current path. These docs are otherwise correct.

- `docs/src/backend/05-REQUEST_FLOW.md:80` — `/auth/me` → `GET /v1/session`
- `docs/src/backend/06-PERMISSION-SYSTEM.md:11, 137, 342` — three `/auth/me` mentions
- `docs/src/backend/permissions/model.md:68, 88` — two mentions (one is a section heading)
- `docs/src/backend/permissions/audit.md:49` — one mention
- `docs/src/backend/04-README.md:89` — API table row `GET /api/v1/users/me` is wrong on two counts (path was `/auth/me`, not `/users/me`; current path is `/v1/session`)
- `docs/src/glossary.md:48` — `/me` glossary entry
- `docs/src/llm-agent-guide.md:71` — agent guide reference
- `docs/src/frontend/01-overview/personas.md:11, 22, 70` — three mentions including two mermaid edges

For each: keep the surrounding sentence, swap the path. If the surrounding sentence explains the auth flow at any length, prune it to a one-sentence cross-link to `architecture/04-auth-flow.md`.

### B) Duplicate-narrative removal

- **`docs/src/backend/01-overview.md`** — three changes:
  - Lines 79-82 (auth endpoint entries in the API table): replace with a single row pointing to the auth flow doc.
  - Lines 144-145 (`OIDC_DISCOVERY_URL` env-config example): update key name to the current setting (`OAUTH_ISSUER_URL`); see `app/core/config.py`.
  - Lines 172-189 (the "Authentication & Authorization" section): delete the multi-step flow description and the wrong `Bearer <token>` claim. Replace with one paragraph: "The backend authenticates users via OIDC + httpOnly session cookies. See [Auth Flow](../architecture/04-auth-flow.md) for the full request flow, claim contract, and security boundaries." Keep the authorization subsection that explains in-code RBAC (that's backend-specific and not duplicated elsewhere).
- **`docs/src/frontend/01-overview.md:62-69`** — section already cross-links to `04-auth-flow.md`, but the prose mentioning `auth/me` should be cut. Replace with one or two sentences describing the SPA's role (driving the OAuth login redirect, landing at `/auth/complete`, reading session state from `useAuthStore`), with a link out to the canonical doc.

## Out of scope

- `docs/src/architecture/04-auth-flow.md` — already correct, do not edit.
- `docs/src/architecture-decision-records/*.md` — each ADR is a frozen decision record. Stale paths in old ADRs (e.g., ADR-012's `/auth/me` examples) reflect the state at the time the decision was made; not updated.
- `docs/src/implementation-plans/*.md` — historical records of past work; intentionally frozen.
- Any backend or frontend code change.
- The `permissions/*` docs' detailed RBAC narrative — that's the canonical place for permissions, leave the structure intact and only fix the path references.

## Verification

1. `cd docs && mkdocs build --strict` succeeds with no broken-link warnings.
2. `grep -rn --include="*.md" -e "/auth/me\|/auth/refresh\|/auth/logout\|users/me\|Bearer <token>" docs/src/ | grep -vE "implementation-plans|architecture-decision-records"` returns zero results (path-only fixes complete; ADRs and plans intentionally retain historical references).
3. After the cleanup, the only place describing the auth flow narrative is `architecture/04-auth-flow.md` — sanity-check by grepping for `"OAuth Authorization Code"` and the `sequenceDiagram` block; only one source file should appear.
4. Open the rendered `backend/01-overview.html` and `frontend/01-overview.html` locally — confirm both still read coherently end-to-end (the auth sections become cross-link callouts, not gaps).

## Delivery

Single PR titled `docs: single source of truth for auth flow`. ~11 files touched, all in `docs/src/`. No code, no test changes.
