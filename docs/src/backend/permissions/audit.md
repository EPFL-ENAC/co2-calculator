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

- `require_permission` — emits a `Permission check denied` warning log on
  deny, with `user_id`, the required `path`, and the requested `action`
  (see [`app/core/security.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/core/security.py)).
- `get_data_filters` — emits `data_filter` events with the chosen scope
  (`global` / `unit` / `own`) and the resulting filters dict.
- `check_resource_access` — emits `resource_access` events with the
  resource type, the resource snapshot fields used by policy, and the
  policy decision plus its `reason` string.
- HTTP 403 responses carry a generic `{"detail": "Permission denied"}`
  body — the missing `path.action` is **not** echoed to the client. To
  identify which permission was missing, inspect the server-side
  `Permission check denied` log entry (it carries `path` and `action` in
  its `extra` payload).

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

The 403 body is generic, so debugging starts with the server log.

1. Find the most recent `Permission check denied` warning in the API logs
   for the request's `user_id` and `request_id`. Its `extra` payload
   carries the required `path` and `action`.
2. Call `/api/v1/auth/me` with the user's token and inspect the flat
   `permissions` dict — look for a key matching `path` (or
   `path/<institutional_id>` for module permissions) whose action list
   contains `action`.
3. If the grant looks correct but the request still fails, check the most
   recent `resource_access` event for the reason string (e.g.
   `API trips are read-only`, `Insufficient permissions`).
4. If no `permission_check` deny event is present at all, suspect token
   expiry or an upstream auth failure — re-authenticate and retry.

## Migrating legacy role checks

Legacy `User.has_role(...)` call sites should be migrated to the
permission-based helpers. Grep for `has_role(` across `backend/app` and
replace with `require_permission` (route layer), `get_data_filters`
(service layer), or `check_resource_access` (resource layer). See
[how-to-add](./how-to-add.md) for the target shape.

## Where the policy lives

- Decorator: [`app/core/security.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/core/security.py).
- Filters & resource policy:
  [`app/services/authorization_service.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/services/authorization_service.py)
  and [`app/core/policy.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/core/policy.py).
- Permission calculation:
  [`app/models/user.py::calculate_user_permissions`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/models/user.py).
- Permission check helper:
  [`app/utils/permissions.py::has_permission`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/utils/permissions.py).
