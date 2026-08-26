---
status: delivered
issue: 2369
last_updated: 2026-08-26
summary: >
  Let the backend decide workspace-unit access in the router guard: when the
  route's unit is not in the membership list, fetch it via GET /units/{id}
  (policy-authorized) instead of redirecting client-side. Fixes superadmin
  being bounced from units outside their membership list.
---

# 2369 — Superadmin redirected away from non-member units (guard authorized client-side)

## Context

A global-scope user (e.g. superadmin) opening
`/{lang}/{unitId}-{slug}/{year}/…` for a unit they hold no `UnitUser`
membership row in was silently redirected to the landing resolver.

Two layers on the authorization path:

1. `validateUnit()` (`frontend/src/router/guards/validateUnitGuard.ts`) only
   accepted units present in `workspaceStore.units`, populated from
   `GET /api/v1/users/units` — a client-side authorization decision, violating
   the invariant "the frontend never checks roles; the backend decides"
   ([guardrails](../contributing/guardrails.md)).
2. `UnitService.get_user_units` inner-joins `UnitUser` on `user_id`, so the
   list is membership-scoped regardless of role — a superadmin never receives
   units they aren't members of.

## Fix (frontend-only, backend stays the decision-maker)

- **`frontend/src/utils/resolveWorkspaceUnit.ts`** (new): pure leaf helper.
  Membership list is a fast path; any other parsable unit id is resolved by
  asking the backend. Kept free of store/api imports so the regression test
  runs node-side under Playwright (repo has no Vitest).
- **`frontend/src/router/guards/validateUnitGuard.ts`**: `validateUnit()` now
  calls the helper, passing a `fetchUnit` backed by
  `workspaceStore.getUnit(id)` → `GET /api/v1/units/{id}`, which runs policy
  authorization server-side (`UnitService.get_by_id` →
  `query_policy("authz/resource/read")`). 200 → `setUnit()` and proceed;
  403/404 → the existing workspace-setup redirect.
- **`frontend/src/stores/workspace.ts`**: `getUnit` (sole caller is this
  guard flow) passes `skipErrorCodes: [403, 404]` — refusal is an expected
  outcome handled by the guard, not a toast.
- **`frontend/src/api/http.ts`**: the global 403 hook (toast + hard
  `location.replace('/unauthorized')`) now honors `skipErrorCodes` like the
  generic error branch already did, so a caller that declared 403 expected
  gets the `HTTPError` instead of a hard redirect. No existing caller passed
  403, so behavior is unchanged elsewhere.

## Rest of the flow (verified, no change needed)

After the guard passes, the workspace loads
`GET /carbon-reports/unit/{id}/year/{y}/` (create on 404) and
`GET /carbon-reports/{id}/modules/`. All of these enforce
`require_unit_access` (`backend/app/core/policy.py`), which explicitly allows
global-scope roles — so a superadmin's workspace on a non-member unit loads
end to end. No backend change shipped.

## Regression test

`frontend/tests/unit/validate-unit-resolution.spec.ts` (Playwright unit
suite, `npm run test-ct`): pins that a member unit resolves without a backend
call, that a non-member unit allowed by the backend resolves (the reported
bug — resolved to `null`/redirect before the fix), that a backend refusal
still redirects, and that an unparsable unit param never reaches the backend.

## Parked follow-ups (permission scoping — waits for the lead)

- `authz/resource/read` in `backend/app/core/policy.py` is still the legacy
  allow-all stub, so `GET /units/{id}` returns 200 for any authenticated
  user. The guard therefore currently admits any user to the URL, and the
  first workspace data call (`require_unit_access`) 403s non-members —
  visible refusal via the global 403 handling, not a silent wrong page.
  Implementing a real read policy (global scope or unit-scoped role) will
  make the guard's 403 → workspace-setup redirect path active. Do not widen
  or tighten this while the lead is away.
- Latent, pre-existing: the guard's `GET users/units` call uses the default
  `limit=100`; a user with >100 visible units would previously have been
  redirected for units past the cap. The backend probe added here masks the
  user-facing symptom (the unit now resolves via `GET /units/{id}`), but the
  membership list itself is still truncated for such users (e.g. in the
  workspace selector).
