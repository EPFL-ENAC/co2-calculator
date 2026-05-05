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
- **Actions**: `view` (read), `edit` (create/update/delete),
  `export` (data export), `sync` (trigger imports — `data_management` only).

Backoffice scoping by sub-perimeter is being refined under issue #459, which
will narrow `backoffice.*` permissions to a sub-perimeter rather than a flat
global grant.

## Roles

Roles are assigned to users and determine which permissions they receive:

- `co2.user.std` — Standard user, own-scope access (professional travel only).
- `co2.user.principal` — Unit manager, unit-scope access (all modules).
- `co2.backoffice.metier` — Backoffice administrator with reporting and
  data-management access.
- `co2.superadmin` — Super administrator with full system + backoffice access.

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

```json
{
  "permissions": {
    "backoffice": {
      "users":            {"view": false, "edit": false},
      "reporting":        {"view": true,  "export": true},
      "data_management":  {"view": true,  "edit": true, "export": true, "sync": true},
      "documentation":    {"view": true,  "edit": false}
    },
    "modules": {
      "headcount":           {"view": true, "edit": true},
      "professional_travel": {"view": true, "edit": true, "export": false}
    }
  }
}
```

Permissions are calculated in-memory on each `/auth/me` call — they are
never stored in the database. See
[`app/utils/permissions.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/utils/permissions.py)
for the calculation logic and
[`app/core/security.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/core/security.py)
for the `require_permission()` decorator.

## When to use what

- **Route-level checks** (`require_permission`) — most common; reject
  requests at the door.
- **Service-level filtering** (`get_data_filters`) — automatic scope
  filtering for list/query operations.
- **Resource-level checks** (`check_resource_access`) — per-record rules
  for update/delete or business invariants.

See also: [matrix](./matrix.md), [how-to-add](./how-to-add.md),
[audit](./audit.md).
