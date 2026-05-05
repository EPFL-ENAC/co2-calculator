---
status: delivered
last_updated: 2026-05-05
summary: /me is a pure DB read; /refresh triggers async role sync with 15-minute TTL eventual consistency.
---

# ADR-017: `/me` is a Pure DB Read; `/refresh` Triggers Async Role Sync

**Status**: Accepted
**Date**: 2026-05-05
**Deciders**: Backend Team, Auth Lead
**Related**: [ADR-005: Authorization Strategy](./005-authorization-strategy.md), [ADR-012: JWT Authentication](./012-jwt-authentication-strategy.md); plan `docs/src/implementation-plans/334-me-performance-optimization.md`; `docs/role-sync-architecture.md`

## Context

`/me` previously fetched the user, then synchronously called the
external role provider (Accred) to refresh roles before returning.
Latency averaged ~1000ms per call, every call. Frontends polled
`/me` aggressively, multiplying load on Accred and on our request
threads. A single Accred outage stalled every authenticated page.

We needed `/me` to be cheap enough that the frontend could call it
freely, while keeping role data fresh enough for authorization
decisions that already use the database row, not the JWT claims.

## Decision

Split the responsibilities:

- **`/me`** validates the JWT, reads the user row (with cached
  roles), and returns. **No external calls.** Target latency ~8ms.
- **`/refresh`** validates the JWT, reads the user row, and triggers
  background role sync via FastAPI `BackgroundTasks`. Returns
  immediately with the currently cached roles.

Background `RoleSyncService`:

- Runs only if `last_roles_sync_at` is older than 15 minutes (TTL),
  preventing sync storms.
- Fetches fresh roles from the configured provider.
- Diffs against cached roles; writes only on change; updates
  `last_roles_sync_at` on success.
- Failures are logged but never block the response.

Authorization always reads `User.roles` from the database, so the
guarantee is **eventual consistency within 15 minutes**, not
strict freshness. Operators can force a sync by hitting `/refresh`.

See `docs/src/implementation-plans/334-me-performance-optimization.md`
and `docs/role-sync-architecture.md`.

## Consequences

**Positive**:

- `/me` p95 dropped from ~1000ms to ~8ms.
- Accred outages no longer cascade into authenticated routes.
- External API call rate dropped from "per request" to "per 15 min
  per active user".
- Frontends can poll `/me` freely (used for tab focus, route
  guards, etc.).

**Negative**:

- Role changes on the provider are visible after up to 15 minutes
  unless the user (or admin) hits `/refresh`.
- A new `last_roles_sync_at` column and the `RoleSyncService` add
  surface area; covered by unit tests in `334`'s Task 2.
- Background errors are silent to the caller (logged only); we
  accept this in exchange for endpoint reliability.

## References

- `docs/src/implementation-plans/334-me-performance-optimization.md`
- `docs/role-sync-architecture.md`
- [ADR-005: Authorization Strategy](./005-authorization-strategy.md)
