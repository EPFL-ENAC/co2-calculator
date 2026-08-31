---
status: delivered
issue: 2570
last_updated: 2026-08-31
title: "Let the workspace guard handle a refused unit instead of the HTTP layer"
summary: "GET /units/{id} answering 200 means the user may read a unit, not enter its workspace. The workspace-home call is the real authorization boundary and was issued without skipErrorCodes, so a 403 there triggered the global toast + hard redirect to /unauthorized before the guard's own soft redirect could run."
---

# Let the workspace guard handle a refused unit instead of the HTTP layer

## Problem

A user with valid roles lands on `/unauthorized` when their persisted workspace
selection points at a unit they may read but not enter. Seen on stage after the
database was dropped and reseeded: unit ids moved, and every returning user's
`workspaceLocalStorage` still named the old one.

Trace `029247`:

```
GET /v1/session                   200
GET /v1/year-configuration/       200
GET /v1/units/996                 200   <- unit probe SUCCEEDS
GET /v1/workspace/996/2025/home   403   <- workspace load REFUSED
```

The user holds `calco2.user.principal` on unit 1953 and `calco2.user.standard`
on 1905. They should have landed in 1953.

## Root cause

`validateUnit()` (`router/guards/workspaceGuard.ts`) probes the backend for a
unit outside the membership list (#2369) via `GET units/{id}`, which answers
**200** — reading a unit is not permission to open its workspace. The real
boundary is `GET workspace/{unit}/{year}/home`, one call later.

That call, `fetchWorkspaceHome` in `stores/workspace.ts`, was issued **without
`skipErrorCodes`**. The `afterResponse` hook in `api/http.ts` therefore treated
its 403 as a page-access denial: `Notify.create` + `location.replace` to
`/unauthorized`.

The guard already handles this correctly — `fetchWorkspaceHome` catches,
returns `null`, and `loadWorkspaceFromRoute` redirects to the landing resolver,
which picks a unit the user _can_ access. **It never gets the chance**: the hard
redirect in the HTTP layer wins the race.

#2369 gave the sibling call exactly this treatment and stopped there:

```ts
// 403/404 are expected — the unit guard probes units outside the
// membership list (#2369) and redirects on refusal. No global toast.
.get(`units/${id}`, { skipErrorCodes: [403, 404] })
```

Same guard, same expected-refusal path, same file — one call site fixed, the
other missed.

The stale selection is only the trigger. Any unit a user can read but not enter
reproduces this, with or without a database drop.

## Design

Add `skipErrorCodes: [403, 404]` to the `fetchWorkspaceHome` request. One line;
every other piece of the recovery path already exists and is already correct.

Deliberately **not** done: clearing the persisted `selectedParams` on refusal.
The redirect re-enters `loadWorkspaceFromRoute`, which overwrites them from the
new route, so the stale value self-heals on the next successful load. Clearing
it would be a second mechanism for an outcome the first already guarantees.

## Steps

- [x] `skipErrorCodes: [403, 404]` on the workspace-home request
      (`frontend/src/stores/workspace.ts`).
- [x] Regression test: `frontend/tests/integration/workspace-refused-unit.spec.ts` + `setup/workspace-refused-unit-mocks.ts`. Mocks the exact asymmetry from
      the trace — `units/996` 200, `workspace/996/2025/home` 403 — and asserts
      the app lands on the user's own unit, shows no toast, and never reaches
      `/unauthorized`.
- [x] `make lint` and `make type-check` green.
- [ ] Run the integration suite. Not executed here — it needs a production
      build and the `npm run preview` webServer. `npm run test:e2e -- workspace-refused-unit`.

## Open

- `useResultsPrintData.ts` and `useSimulationExplorePrintData.ts` still do the
  **pre-#2369 client-side membership check** (`units.find(...)`, no backend
  fallback), which contradicts "the frontend never checks roles". A global-scope
  user printing a non-member unit's results gets a blank page. Not fixed here —
  it is a different code path with a different failure mode, and deserves its
  own issue rather than being folded into a one-line guard fix.

## Related

- [#2369](./2369-superadmin-unit-workspace-access.md) — added the backend probe this
  builds on; fixed `getUnit`, missed `fetchWorkspaceHome`.
