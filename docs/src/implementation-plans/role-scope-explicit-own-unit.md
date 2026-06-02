---
status: in-progress
issue: TBD
last_updated: 2026-06-02
title: "Explicit RoleScope: own / unit / global"
summary: "Replace the implicit role→scope coupling with a discriminated-union Scope (global/unit/own/affiliation) so the own↔unit boundary is explicit in both the schema and the permission key, fixing unit-level capability leaking to standard users."
---

## Problem

Scope level (own / unit / global) is **implicit** today: the same
`RoleScope(institutional_id="0184")` means **unit** for a principal but
**own** for a standard user — the level is decided by the _role_, not the
scope object. Consequences:

- `calco2.user.principal` and `calco2.user.standard` get the **same** key
  shape, `modules.X/<unit_iid>` (`role_provider.py` assigns the unit id to
  both; `user.py` uses the same `scope_key`).
- `check_module_permission_for_unit` looks up `modules.X/<unit_iid>`, so
  **both** match — a unit-level operation (e.g. PATCH module status) cannot
  tell a principal from a std.
- Own-scope is only enforced later, in `get_data_filters` (std →
  `{"user_id", scope:"own"}`) and the resource policy (`created_by`). It is
  absent from the key, so the route/permission layer is blind to it.

This is why a std user leaks unit-level capability through `edit` (std holds
`edit` on `professional_travel` + `external_cloud_and_ai`).

## Design

Make scope explicit, mirroring the [matrix](../backend/06-PERMISSION-SYSTEM.md#role-permission-matrix)
(Global / Unit `U` / Own `O` + backoffice affiliation). `Role.on` becomes a
Pydantic **discriminated union** keyed by `kind`:

```python
class GlobalScope(BaseModel):
    kind: Literal["global"] = "global"

class UnitScope(BaseModel):
    kind: Literal["unit"] = "unit"
    institutional_id: str          # the unit

class OwnScope(BaseModel):
    kind: Literal["own"] = "own"
    institutional_id: str          # the unit; owner is always current_user

class AffiliationScope(BaseModel):
    kind: Literal["affiliation"] = "affiliation"
    affiliation: str               # ACCRED LVL3

Scope = Annotated[
    Union[GlobalScope, UnitScope, OwnScope, AffiliationScope],
    Field(discriminator="kind"),
]
```

**Who vs. where:** the _owner_ is always `current_user` (never stored — it
would be redundant and could go stale); the _unit_ is explicit on both
`UnitScope` and `OwnScope` (preserves ACCRED data, supports multi-unit std,
enables an explicit cross-unit 403 rather than an empty own-filtered list).

### Key shapes

The breadth must live in the key, because `calculate_permissions()` returns a
flat dict that is the sole source of truth for both the backend resolver and
the frontend.

| Role      | scope             | key                       | breadth          |
| --------- | ----------------- | ------------------------- | ---------------- |
| global    | `GlobalScope`     | `modules.X`               | all              |
| principal | `UnitScope`       | `modules.X/<unit>`        | all unit records |
| std       | `OwnScope`        | `modules.X/<unit>/own`    | own records only |
| metier    | `AffiliationScope`| `backoffice.reporting/<aff>` | sub-perimeter |

### Resolver

Add `resolve_module_scope(user, module, action, unit_id) -> "global"|"unit"|"own"|"denied"`
by which key matched (bare → global; `…/<unit>` → unit; `…/<unit>/own` →
own). Then:

- **Unit-level ops** (PATCH module status) require `unit`/`global` → principal
  and superadmin pass, std (`own`) is excluded — no new action, no `edit`/`sync`
  overload.
- **Record ops** (std's own travel CRUD) accept `own`/`unit`/`global`; an
  `own` match applies the existing `created_by == current_user` filter.

## Changes

1. **`app/models/user.py`** — the union; rewrite `as_scope_key` (own →
   `/<unit>/own`); replace `is_global_scope`/`is_role_scope`/
   `is_affiliation_scope` with `match scope.kind`; std branch emits `OwnScope`
   keys, principal `UnitScope`, metier `AffiliationScope`, superadmin bare.
2. **`app/providers/role_provider.py`** — emit the right scope kind per role
   in Accred / Default / Test providers.
3. **`app/utils/permissions.py`** — `has_permission` learns the `…/<unit>/own`
   suffix; `derive_backoffice_affiliations` unchanged (affiliation).
4. **`app/core/policy.py`** + **`app/services/authorization_service.py`** —
   `resolve_module_scope`; `check_module_permission(_for_unit)` gates by
   required breadth; `get_data_filters` maps `own`→`created_by`.
5. **`app/api/v1/carbon_report_module.py`** — PATCH status requires unit scope.
6. **Frontend** — `permission.ts` helpers parse the `/own` suffix; show
   unit-level controls only for unit/global; regenerate `openapi.d.ts`.
7. **Tests** — migrate every `Role(on=...)` construction; add own-vs-unit
   gating coverage.

## Migration & compatibility

Pre-v1 **drops the DB between deploys**, so the changed `roles_raw` JSON shape
needs **no migration**. Per the no-backward-compat rule this is a **clean cut**
— the old `RoleScope` shape is removed, not dual-pathed.

## Verification

1. Unit: each scope kind → expected key shape; std `…/own`, principal `…/<unit>`.
2. e2e: PATCH status — principal allowed, std denied **even for
   `professional_travel`**; cross-unit principal/std denied; backoffice denied.
3. e2e: std own travel CRUD still works (own match → `created_by` filter);
   cross-unit std → 403 (not empty-200).
4. Full `uv run pytest` green; frontend `make type-check` green.
