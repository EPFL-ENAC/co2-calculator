---
status: delivered
last_updated: 2026-05-05
summary: Roles, scopes, and the structure of permission grants.
---

# Permission Model

## Permissions

Permissions use dot-notation paths combined with an action:

- **Paths**: `backoffice.users`, `backoffice.reporting`,
  `backoffice.data_management`, `backoffice.documentation`,
  `modules.headcount`, `modules.professional_travel`, ...
  Module paths can additionally be unit-scoped via a trailing
  `/<institutional_id>` segment (e.g. `modules.headcount/0184`).
- **Actions**: `view` (read), `edit` (create/update/delete),
  `export` (data export), `sync` (trigger imports — granted on
  `backoffice.data_management` for backoffice/superadmin and on every
  `modules.*` for principals).

Backoffice scoping by sub-perimeter is being refined under issue #459, which
will narrow `backoffice.*` permissions to a sub-perimeter rather than a flat
global grant.

## Roles

Roles are assigned to users and determine which permissions they receive:

- `calco2.user.standard` — Standard user, own-scope access (professional
  travel and external cloud / AI).
- `calco2.user.principal` — Unit manager, unit-scope access (all modules).
- `calco2.backoffice.metier` — Backoffice administrator with reporting and
  data-management access.
- `calco2.superadmin` — Super administrator with full system + backoffice
  access (no `modules.*` grants).

The canonical role identifiers live in the `RoleName` enum in
[`app/models/user.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/models/user.py).

## Scopes

Scopes determine which **data records** a user can see:

- **Global** — see everything (super admin, backoffice metier).
- **Unit** — see records for assigned units (principals).
- **Own** — see only records the user created (standard users).

`get_data_filters()` translates the scope into structured filters:

```python
# Global
{}
# Unit
{"unit_ids": ["12345", "67890"]}
# Own
{"user_id": "user-123"}
```

## Resources

A *resource* is a single data record (a specific headcount entry, a single
travel record, etc.). Resource-level policy can enforce business rules that
generic permission checks cannot, e.g. "API trips are read-only" — see
[audit](./audit.md) and [matrix](./matrix.md).

## Permission shape (`/auth/me` response)

The backend returns a **flat** dictionary keyed by dot-notation path, with a
**list of action strings** as the value. Module paths carry a trailing
`/<institutional_id>` segment for unit-scoped grants; `backoffice.*` and
`system.*` grants are always un-scoped.

```json
{
  "permissions": {
    "backoffice.reporting":       ["view", "export"],
    "backoffice.users":           ["view", "edit", "export"],
    "backoffice.data_management": ["view", "edit", "export", "sync"],
    "backoffice.documentation":   ["view", "edit"],
    "modules.headcount/0184":     ["view", "edit", "sync"],
    "modules.professional_travel/0184": ["view", "edit", "sync"]
  }
}
```

Permissions are calculated in-memory on each `/auth/me` call — they are
never stored in the database. The role-to-permission mapping lives in
[`app/models/user.py::calculate_user_permissions`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/models/user.py),
the runtime check helper is
[`app/utils/permissions.py::has_permission`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/utils/permissions.py),
and the FastAPI dependency
[`app/core/security.py::require_permission`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/core/security.py)
wires it into routes.

## When to use what

- **Route-level checks** (`require_permission`) — most common; reject
  requests at the door.
- **Service-level filtering** (`get_data_filters`) — automatic scope
  filtering for list/query operations.
- **Resource-level checks** (`check_resource_access`) — per-record rules
  for update/delete or business invariants.

See also: [matrix](./matrix.md), [how-to-add](./how-to-add.md),
[audit](./audit.md).
