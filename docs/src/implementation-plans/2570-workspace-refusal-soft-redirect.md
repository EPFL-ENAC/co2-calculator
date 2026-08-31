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
**200 — for everyone**. Not because reading a unit is a lesser permission than
entering it, but because `authz/resource/read` is still the legacy allow-all
stub (#2379):

```python
# Legacy/fallback: For resource and unit policies, return basic allow
"allow": True if filters is not None else True,  # Default allow for now
```

So the probe authorizes nothing, and #2369's "the backend decides" delegation is
currently vacuous. Every non-member unit reaches `GET
workspace/{unit}/{year}/home` — the only call on this path that actually
enforces anything, via `require_unit_access`.

#2379 predicted this exact incident when it was filed on 2026-08-26:

> the first workspace data call (`require_unit_access`) 403s non-members —
> **visible refusal via the global 403 handling**, not a silent wrong page

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

Also clear the persisted `selectedParams` on both refusal paths.

The first version of this plan argued against it — "the redirect re-enters
`loadWorkspaceFromRoute`, which overwrites them from the new route, so the stale
value self-heals". That reasoning only covered the **derived** state.
`validateUnit()`'s failure branch already clears `selectedUnit` and
`selectedYear`, but `selectedParams` is the one field that is _persisted_
(`workspaceLocalStorage`) — and it was left pointing at the refused unit.

`ErrorNotFound.vue` reads it back for its "home" link, on a page where no guard
runs to refresh it. So the stale selection survives a reload and sends the user
straight back to the unit they cannot enter. Clearing it is not a second
mechanism: it is finishing the one that already exists, in the same two
branches.

The `!carbonReportId` branch matters more than the `validateUnit()` one here —
that is the #2570 path, where the probe answers 200 and the workspace call 403s,
and it cleared nothing at all.

### The bounce this fix would otherwise introduce

Making the refusal soft exposes a second defect that the hard redirect was
hiding. `redirectToDefaultRoute` picks `workspaceStore.units[0]` and the newest
open year — deterministically. If _that_ workspace also fails (403, or a 200
carrying `carbon_report_id: null`, which lands in the same `!response ||
!carbonReportId` branch), the guard redirects to the resolver, the resolver hands
back the same route, and it cycles.

Observed, against a build carrying the two fixes above but not this one: the app
does not visibly bounce — vue-router aborts the cycle and it **sits on the
original URL rendering nothing**, which is worse than a redirect loop because
there is nothing to see.

Bounded with a stateless check: the resolver's pick is knowable from inside the
guard, so `isLandingResolverPick(to)` asks "is the place I would send you the
place that just failed?" and returns `/unauthorized?reason=workspace-refused`
instead. No retry counter, no marker in the query string, no state to keep in
sync.

`from` cannot be used for this: vue-router keeps `from` as the _original_ route
through a redirect chain, so it is identical on the second bounce and the tenth.

## Steps

- [x] `skipErrorCodes: [403, 404]` on the workspace-home request
      (`frontend/src/stores/workspace.ts`).
- [x] Bound the redirect to one attempt (`isLandingResolverPick` in
      `router/guards/workspaceGuard.ts`) + new `workspace-refused` reason in
      `utils/unauthorized.ts` and its i18n message (en + fr, single file).
- [x] Clear the persisted `selectedParams` on both refusal paths
      (`router/guards/workspaceGuard.ts`); `setSelectedParams` now accepts
      `null`. Asserted in the regression test by reading
      `workspaceLocalStorage` back after the redirect.
- [x] Regression test: `frontend/tests/integration/workspace-refused-unit.spec.ts` + `setup/workspace-refused-unit-mocks.ts`. Mocks the exact asymmetry from
      the trace — `units/996` 200, `workspace/996/2025/home` 403 — and asserts
      the app lands on the user's own unit, shows no toast, and never reaches
      `/unauthorized`.
- [x] `make lint` and `make type-check` green.
- [x] Ran the integration suite (`npx playwright test
tests/integration/workspace-refused-unit.spec.ts`) against a real
      `quasar build` + `vite preview`. Against a build without the bounce
      guard: 1 passed, 1 failed, stuck on the original URL for the full 15s
      timeout. With it: 2 passed in 2.3s.

## Open

- `useResultsPrintData.ts` and `useSimulationExplorePrintData.ts` still do the
  **pre-#2369 client-side membership check** (`units.find(...)`, no backend
  fallback), which contradicts "the frontend never checks roles". A global-scope
  user printing a non-member unit's results gets a blank page. Not fixed here —
  it is a different code path with a different failure mode, and deserves its
  own issue rather than being folded into a one-line guard fix.

## Related

- [#2369](./2369-superadmin-unit-workspace-access.md) — added the backend probe
  this builds on; fixed `getUnit`, missed `fetchWorkspaceHome`.
- #2379 — the allow-all read stub that makes the probe answer 200 for everyone,
  and the `users/units` `limit=100` truncation. Fixing its part 1 turns the
  probe into real authorization, so refusals move one call earlier onto the
  `getUnit` path that #2369 already handles. This fix stays necessary either
  way: it is what makes a refusal on the workspace call a soft redirect rather
  than a dead end.
