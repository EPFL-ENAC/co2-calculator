---
status: delivered
issue: 2379
last_updated: 2026-08-31
title: "Real read policy for GET /units/{id}, and stop truncating the membership list"
summary: "Route the unit read check through require_unit_access — the same enforcer as the workspace boundary — instead of the legacy allow-all policy stub, and drop the limit=100 pagination that silently truncated the membership list in four call sites including the session bootstrap."
---

# Real read policy for GET /units/{id}, and stop truncating the membership list

## Problem

Two backend gaps deliberately left by #2369/#2370, tracked here since
2026-08-26 — and part 1 predicted the 2026-08-31 incident (#2570) verbatim:

> the first workspace data call (`require_unit_access`) 403s non-members —
> **visible refusal via the global 403 handling**, not a silent wrong page

1. **`authz/resource/read` is the legacy allow-all stub.** `query_policy` in
   `backend/app/core/policy.py` routes only permission/access/data policies;
   everything else — including this one — falls into:

   ```python
   # Legacy/fallback: For resource and unit policies, return basic allow
   "allow": True if filters is not None else True,  # Default allow for now
   ```

   So `GET /units/{id}` answers 200 for **any** authenticated user, the
   workspace guard's probe (#2369) authorizes nothing, and a recycled unit id
   in a stale persisted selection is indistinguishable from a legitimate unit
   until the workspace call refuses it one hop later (#2570, trace 029247).

2. **`get_user_units` truncates at `limit=100`** — and not just where the
   issue spotted it. Four call sites, two of them silent:

   | caller                              | limit passed             | consequence past 100 memberships                      |
   | ----------------------------------- | ------------------------ | ----------------------------------------------------- |
   | `GET /users/units` (users.py)       | query param, default 100 | workspace selector truncates                          |
   | `GET /units` (units.py)             | query param, default 100 | same list, same truncation                            |
   | **`auth.py` session bootstrap**     | **none → default 100**   | the `units` hydrated at login are silently incomplete |
   | **`carbon_report_module_stats.py`** | **none → default 100**   | accessible-unit filter silently narrows past 100      |

   A truncated authorization-adjacent list that _looks_ complete is the
   no-silent-fallbacks failure mode.

## Design

### Part 1 — reuse the workspace enforcer, don't grow a second rule

`UnitService.get_by_id` already loads the unit, asks `query_policy`, and
honors `decision.allow` — only the decision is fake. Replace the ceremony with
a direct call to **`require_unit_access(user, unit)`** (`core/policy.py`), the
same function that guards `GET /workspace/{unit}/{year}/home`:

- global-scope roles pass;
- any role scoped to the unit's `institutional_id`
  (`pick_role_for_institutional_id`) passes;
- otherwise 403.

Why not a real `_evaluate_resource_read_policy` routed inside `query_policy`?
Because it would be a **second copy of the same rule**, and drift between the
probe and the workspace boundary is exactly the bug class #2570 came from.
Reusing the enforcer makes the probe _predict_ the workspace call by
construction — they cannot disagree, ever. The issue's stated rule ("global
scope or unit-scoped role") is precisely `require_unit_access`.

Two consequences, both intended:

- **The end-to-end access set is unchanged.** Anything the probe now refuses,
  the workspace call already refused. Only _where_ the refusal happens moves —
  one call earlier, onto the `getUnit` path that #2369 built and #2571 made
  refusal-safe (soft redirect, cleared persisted selection, bounded retry).
- **A superadmin opening a non-member unit still works end-to-end** — global
  scope passes both the probe and the workspace call. #2369's acceptance
  criterion holds.

Subtlety kept from the old code: `require_unit_access` lets global-scope roles
through **before** its own `None` check, so `get_by_id` keeps its explicit
404-on-missing ahead of the call — otherwise a superadmin probing a deleted id
would get a phantom success.

The unused `unit` branch of `_build_policy_input` and the
`authz/resource/read` line in `query_policy`'s docstring go with it — nothing
routes that name any more.

### Part 2 — delete the pagination, don't tune it

The list is bounded by the user's own membership rows joined at level 4 — a
person cannot hold more roles than EPFL has labs. No frontend caller ever
passes `skip`/`limit`; the only consumer that did is the locust perf helper,
which paginates purely to work around the cap it is now free of. Any limit is
a cliff with a silent fallback on the far side; a bounded-by-construction
query needs none.

So: drop `skip`/`limit` from `get_user_units`, from both list routes, and from
the locust helper (single unpaginated GET). FastAPI ignores unknown query
params, so any stale caller sending `?skip=&limit=` keeps working and simply
receives the full list.

## Steps

- [x] `get_by_id` calls `require_unit_access`; explicit 404 stays first
      (`backend/app/services/unit_service.py`).
- [x] Drop the dead `unit` param from `_build_policy_input`; drop the
      `authz/resource/read` docstring line in `core/policy.py`.
- [x] Remove `skip`/`limit` from `get_user_units` and both list routes
      (`api/v1/units.py`, `api/v1/users.py`).
- [x] Locust `_list_all_units` becomes one unpaginated GET
      (`tests/performance/locustfile.py`).
- [x] Regression tests (`tests/unit/services/test_unit_service.py`):
      non-member 403 (fails on the allow-all stub), member-by-scoped-role 200,
      global-scope 200 without membership, global-scope + missing id 404, and
      101-membership list comes back complete (fails on the truncation).
- [x] `make lint` + `make type-check` green; touched test files pass.

## Not in scope

- `get_user_units` stays membership-scoped (the `UnitUser` inner join). Making
  the _list_ global-aware for backoffice roles is #2369's old item 2 and a
  product decision about what the workspace selector should show a superadmin
  — nothing in the guard needs it, since the probe now handles any unit not in
  the list, correctly.
- The frontend needs no change: #2571 already treats a probe 403 as a soft
  redirect.

## Guardrails note

"Permission scoping needs a written plan reviewed by both maintainers / defer
while the lead is away" — this plan was written first and implemented on the
maintainer's explicit instruction, and the change _narrows_ access on one
endpoint by reusing the already-reviewed enforcer rather than authoring a new
rule. The access set a user can actually reach (probe + workspace call
together) is unchanged.

## Related

- #2369 / [plan](./2369-superadmin-unit-workspace-access.md) — the frontend
  probe this makes real.
- #2570 / [plan](./2570-workspace-refusal-soft-redirect.md) — the incident the
  stub caused, and the refusal-handling this lands on top of.
