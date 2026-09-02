---
status: delivered
issue: 2607
last_updated: 2026-09-01
title: "Planner: mirror PlanPolicy in the delete gate, and stop the permission snapshot going stale"
summary: "Closes the two ways the planner delete button could be enabled while the backend answers 403: canDeletePlan now resolves the permission breadth and applies PlanPolicy.can_delete's rule (global, else creator-only) instead of accepting any delete grant, and the workspace-home aggregate carries freshly computed permissions so the SPA stops gating affordances on the login-time snapshot. No schema change, no product-rule change."
---

# Planner: mirror `PlanPolicy` in the delete gate

Follow-up to the permissions review in
[#2607](https://github.com/EPFL-ENAC/co2-calculator/issues/2607), on top of
[#2043](2043-planner-plan-policy-permission.md).

## Problem

The delete button in `CO2ProjectPlanner.vue` gates on `canDeletePlan`, a
frontend mirror of the backend `PlanPolicy.can_delete`. The two had drifted in
shape, in a way no current role exercises but nothing prevents:

1. **`canDeletePlan` accepted any `delete` grant, at any breadth.** A
   `planner.plans/<cf>: [delete]` key made it return `true` for every visible
   plan, including a colleague's shared one, while `PlanPolicy.can_delete`
   short-circuits on `global` breadth only and otherwise falls back to
   `created_by == user_id` → an enabled button and a 403. The branch is dead
   today (principals hold `delete` at `/own`), so this was latent: the first
   role to gain unit-breadth delete would have surfaced it as a bug report.
2. **The permission payload goes stale within a session.** `bootstrap()`
   snapshots `user.permissions` at login while the backend recomputes them from
   `roles_raw` on every request. An ACCRED role change or a `role_sync_service`
   run mid-session leaves the SPA gating affordances on the old keys until a
   hard reload; for the planner that means an enabled delete button whose call
   `PlanPolicy.for_unit` refuses with 403 "Access to this unit is not
   permitted." This one is live, and not planner-specific — the planner is
   just where it surfaces as a hard 403 rather than a shorter list.

Compounding both: plan 2043's Tests section listed
`frontend/tests/unit/planner-delete-permission.spec.ts`, but the file was never
committed. `canDeletePlan` had no test coverage at all, which is why (1) went
unnoticed.

## Decision

No product-rule change and no backend rule change. Deletion stays creator-only
below global breadth — that is the deliberate #1930 / #2043 rule ("principals
get `delete` at own breadth on purpose so a principal still cannot delete a
colleague's plan"). The fix is to make the frontend mirror structurally
correct, and to stop the snapshot ageing.

## Changes

### `canDeletePlan` resolves the breadth first

`frontend/src/utils/permission.ts` gains a private `resolvePlanBreadth`
mirroring the backend `resolve_module_scope` (bare > `/<cf>` > `/<cf>/own` >
denied). `canDeletePlan` then applies `PlanPolicy.can_delete`'s rule: `global`
deletes anything, any other breadth is creator-only, `null` denies.

Behaviour is identical for every role emitted today. What changes is what
happens _next time a role changes_: a future unit-breadth `delete` key
degrades to creator-only on both sides, instead of over-permitting on one.

### The home aggregate carries fresh permissions

`WorkspaceHomeResponse` gains `permissions: dict`, filled from
`PlanPolicy.permissions` — the policy the route already builds computes
`current_user.calculate_permissions()`, so the value is free and no second
computation or query is added. `workspaceGuard` fans it into the auth store
via a new `setPermissions` action, next to the `setPlans` / `setConfig` /
`setModuleStates` fan-out it already does.

This rides the aggregate call the guard makes on **every** run, so no XHR is
added and the page budget is untouched. It is the same reasoning already
applied to `configuredYears` for #1558: a value a backoffice admin can flip
mid-session cannot be cached once per bootstrap.

The complementary half was already handled: when a role change removes unit
access outright, the home call itself 403s and the guard's `workspace-refused`
path clears the workspace and redirects.

## What is deliberately not changed

- `PlanPolicy.can_delete` does not learn unit breadth. Granting a role
  unit-wide deletion is a product decision, not a refactor; if it is ever
  wanted, the backend is the place to change and the frontend now follows.
- The button stays rendered-but-disabled. The gate is UX only; the backend
  `DELETE` remains the authority, and a direct API call still gets the real
  answer.
- A plan deleted concurrently, or one that stopped being shared, keeps
  answering **404** rather than 403 — `require()` checks `can_view` first so
  plan ids do not leak.

## Tests

- `frontend/tests/unit/planner-delete-permission.spec.ts` (new, the file 2043
  promised): global breadth; own breadth creator / non-creator; the real
  principal key pair; **unit breadth with `delete`, non-creator → false** (the
  regression, red before this change); no key; no unit context; no user id.
- `backend/tests/unit/v1/test_workspace_home.py::test_payload_carries_freshly_computed_permissions`:
  the payload carries `calculate_permissions()` for the caller's roles.
- Plan 2043's Tests section corrected to point at the file that now exists.
