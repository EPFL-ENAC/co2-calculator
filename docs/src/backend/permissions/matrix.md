---
status: delivered
last_updated: 2026-05-05
summary: Role x resource permission matrix and grant summary.
---

# Permission Matrix

The matrix below summarises which actions each role grants on each resource.
It is the canonical view used to plan UI states and policy tests. Source of
truth is
[`app/utils/permissions.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/utils/permissions.py)
- whenever you change a grant there, update this page in the same PR.

Legend: `V` = view, `E` = edit, `X` = export, `S` = sync, `-` = no grant,
`U` = unit-scoped grant, `O` = own-scoped grant. Backoffice grants are
listed flat (issue #459 will further scope them by sub-perimeter).

## Role x permission matrix

| Permission                       | `co2.superadmin` | `co2.backoffice.metier` | `co2.user.principal` | `co2.user.std` |
| -------------------------------- | ---------------- | ----------------------- | -------------------- | -------------- |
| `backoffice.reporting`           | V, X             | V, X                    | -                    | -              |
| `backoffice.users`               | V, E             | V, E                    | E (U)                | -              |
| `backoffice.data_management`     | V, E, X, S       | V, E, X, S              | -                    | -              |
| `backoffice.documentation`       | V, E             | V, E                    | -                    | -              |
| `system.users`                   | E                | -                       | -                    | -              |
| `modules.headcount`              | V, E             | -                       | V, E (U)             | -              |
| `modules.equipment`              | V, E             | -                       | V, E (U)             | -              |
| `modules.professional_travel`    | V, E, X          | -                       | V, E (U)             | V, E (O)       |
| `modules.buildings`              | V                | -                       | V (U)                | -              |
| `modules.purchase`               | V                | -                       | V (U)                | -              |
| `modules.research_facilities`    | V                | -                       | V (U)                | -              |
| `modules.external_cloud_and_ai`  | V                | -                       | V (U)                | -              |
| `modules.process_emissions`      | V                | -                       | V (U)                | -              |

## Scope summary

| Role                    | Scope  | Notes                                                    |
| ----------------------- | ------ | -------------------------------------------------------- |
| `co2.superadmin`        | Global | Full system + backoffice access                          |
| `co2.backoffice.metier` | Global | All `backoffice.*` (no module data edits)                |
| `co2.user.principal`    | Unit   | All `modules.*` for assigned units; can assign unit role |
| `co2.user.std`          | Own    | Only own records on `modules.professional_travel`        |

## Resource-level policy notes

A user listed as having `edit` on `modules.professional_travel` may still be
denied for a specific trip. Resource-level policy (see [audit](./audit.md))
enforces:

1. **API trips** (`provider == "api"`) are read-only for everyone, including
   super admins.
2. **Global scope** roles can edit any non-API trip.
3. **Principals** can edit manual/CSV trips inside their assigned units.
4. **Standard users** can only edit their own manual trips.

Equivalent rules can be added per resource type — see
[how-to-add](./how-to-add.md).

## Cross-references

- [model](./model.md) — definitions of the symbols used in this matrix.
- [Permission System Overview](../06-PERMISSION-SYSTEM.md) — narrative
  overview, including OPA evaluation.
