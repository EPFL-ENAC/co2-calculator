---
status: delivered
last_updated: 2026-05-05
summary: Audit-trail mechanics, log shape, and debugging recipes.
---

# Audit Trail

Every authorization decision is logged so that reviewers can reconstruct
who attempted what and why a request was allowed or denied. The trail spans
all three checks — route, service, and resource — and uses structured
logging so events can be queried by user, permission, or resource id.

## What gets logged

- `require_permission` — emits `permission_check` events with the user id,
  required `path.action`, the user's calculated grant, and the decision
  (`allow` / `deny`).
- `get_data_filters` — emits `data_filter` events with the chosen scope
  (`global` / `unit` / `own`) and the resulting filters dict.
- `check_resource_access` — emits `resource_access` events with the
  resource type, the resource snapshot fields used by policy, and the
  policy decision plus its `reason` string.
- HTTP 403 responses include the missing permission in the response body
  (`Permission denied: modules.headcount.edit required`) which is the same
  string used in the audit log.

## Decision flow (audit emission points)

1. Request enters FastAPI dependency chain.
2. `require_permission` resolves the user, looks up the calculated
   permission, and logs `permission_check`.
3. On allow, the service computes scope filters and logs `data_filter`.
4. The repository runs the query with those filters.
5. For per-record actions, `check_resource_access` evaluates the OPA-style
   policy and logs `resource_access` with the policy `reason`.
6. The route returns 200/201 (allow) or 403 (deny). Both branches have
   already produced an audit event upstream.

## Debugging a 403

1. Read the response detail — it names the missing permission, e.g.
   `Permission denied: modules.headcount.edit required`.
2. Call `/api/v1/auth/me` with the user's token and verify
   `permissions.modules.headcount.edit` is `true`.
3. If the permission grant looks correct but the request still fails, check
   the most recent `resource_access` event for the reason string (e.g.
   `API trips are read-only`, `Insufficient permissions`).
4. If neither event is present, suspect token expiry — re-authenticate and
   retry.

## Deprecated patterns to flag

The codebase still emits `DeprecationWarning` for legacy role checks
(`User.has_role(...)`, `get_current_active_user_with_any_role(...)`). Run
tests with `pytest -W default::DeprecationWarning` to surface call sites
and migrate them to `require_permission` / `get_data_filters` /
`check_resource_access`. See [how-to-add](./how-to-add.md) for the target
shape.

## Where the policy lives

- Decorator: [`app/core/security.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/core/security.py).
- Filters & resource policy:
  [`app/services/authorization_service.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/services/authorization_service.py)
  and [`app/core/policy.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/core/policy.py).
- Permission calculation:
  [`app/utils/permissions.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/utils/permissions.py).
