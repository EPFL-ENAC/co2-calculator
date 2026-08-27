---
status: delivered
issue: 862
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

| Role      | scope              | key                          | breadth          |
| --------- | ------------------ | ---------------------------- | ---------------- |
| global    | `GlobalScope`      | `modules.X`                  | all              |
| principal | `UnitScope`        | `modules.X/<unit>`           | all unit records |
| std       | `OwnScope`         | `modules.X/<unit>/own`       | own records only |
| metier    | `AffiliationScope` | `backoffice.reporting/<aff>` | sub-perimeter    |

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

## Implementation checklist (handoff)

State as of 2026-06-02. The backend logic is **done and import-verified**; the
remaining work is the **mechanical test migration**, the **frontend**, and
**docs**. A model with limited context can finish from this section alone.

> **This branch carries two intertwined changes** — the page-driven backoffice
> permissions ([#862](./862-backoffice-update-permissions.md)) and this
> RoleScope redesign. The checklist below covers everything still needed to get
> the suite green for both.

### Mapping rules (apply these mechanically)

When migrating a `Role(role=R, on=SCOPE)` construction:

- `R == CO2_USER_PRINCIPAL`, `RoleScope(institutional_id=X)` → `UnitScope(institutional_id=X)`
- `R == CO2_USER_STD`, `RoleScope(institutional_id=X)` → `OwnScope(institutional_id=X)`
- `R == CO2_BACKOFFICE_METIER`, `RoleScope(affiliation=Y)` → `AffiliationScope(affiliation=Y)`
- `R == CO2_SUPERADMIN`, `GlobalScope(scope="global")` or `GlobalScope()` → `GlobalScope()`
- dict forms in `roles_raw`: add a `kind` key —
  `{"institutional_id": X}` → `{"kind": "unit"|"own", "institutional_id": X}` (by role),
  `{"affiliation": Y}` → `{"kind": "affiliation", "affiliation": Y}`,
  `{"scope": "global"}` → `{"kind": "global"}`.
- **Imports**: drop `RoleScope`; import only the specific scope classes used
  (`UnitScope` / `OwnScope` / `AffiliationScope` / `GlobalScope`) from
  `app.models.user`.
- **Key assertions**: a **standard-user** module key gains the `/own` suffix —
  `modules.<m>/<unit>` → `modules.<m>/<unit>/own`. **Principal** keys stay
  `modules.<m>/<unit>` (no suffix). Backoffice/affiliation keys unchanged.
- **Behaviour flips to assert**: std is **denied** unit-level ops (PATCH module
  status) even on `professional_travel`; a principal **passes** module-flow
  reads (`active-pipelines`, `jobs/year`, `jobs/{id}/stream`) because it can
  `sync`; std (no sync) is **denied** those.

### Done (do not redo) — backend

- [x] `app/models/user.py` — `GlobalScope`/`UnitScope`/`OwnScope`/`AffiliationScope`
      discriminated union (`Scope`, `discriminator="kind"`); `RoleScope` removed;
      `as_scope_key` emits `""` / `/<unit>` / `/<unit>/own` / `/<aff>`; role
      branches gated on `scope.kind`.
- [x] `app/providers/role_provider.py` — `_unit_or_own_scope()` helper; principal→`UnitScope`,
      std→`OwnScope`, metier→`AffiliationScope`, superadmin→`GlobalScope`.
- [x] `app/core/policy.py` — data-filter splits `UnitScope`→unit filter vs
      `OwnScope`→own filter; `require_module_unit_scope()` added; imports
      `resolve_module_scope`.
- [x] `app/core/role_priority.py`, `app/services/user_service.py`,
      `app/seed/seed_fake_user_unit.py` — `isinstance(.on, (UnitScope, OwnScope))`.
- [x] `app/providers/test_fixtures.py` — `TEST_ROLES` use explicit scopes.
- [x] `app/utils/permissions.py` — `has_permission` matches the `/own` key when
      `institutional_id` is set; new `resolve_module_scope()`
      (global>unit>own>denied).
- [x] `app/api/v1/carbon_report.py` — status PATCH gated by
      `require_module_unit_scope` (unit/global only); dropped `require_edit_module`.
- [x] `app/utils/scoping.py` — removed broken `can_edit_module`/`require_edit_module`.
- [x] `tests/unit/models/test_user_base_calculate_permissions.py` — migrated, **green**.

### TODO — test migration (each: imports + scope ctor + `/own` assertions)

- [x] `tests/unit/utils/test_permissions.py` — builders + `_modules(own=)` +
      `_STD_KEYS` `/own`; dict-role `kind`; subsumes test → subset semantics.
      **83 passed.**
- [x] `tests/integration/v1/test_permission_scope_e2e.py` — builders migrated.
- [x] `tests/integration/v1/test_unit_gating_e2e.py` — builders + `_user`/
      `_scoped_*_user` now expose real `calculate_permissions`; status-PATCH
      principal 200 / std 403 via `require_module_unit_scope`.
- [x] `tests/integration/v1/test_professional_travel_trips_map.py` — builders migrated.
- [x] `tests/integration/v1/test_headcount_members_permission.py` — builders migrated.
- [x] `tests/unit/core/test_policy.py` — `UnitScope`; dict roles carry `kind`.
- [x] `tests/unit/providers/test_role_provider.py` — emitted scopes assert
      `OwnScope`/`UnitScope`/`AffiliationScope`.
- [x] `tests/unit/services/test_role_sync_service.py` — std `OwnScope`; dict `kind`.
- [x] `tests/unit/services/test_user_service.py` — generic builder `UnitScope`;
      no-id role → `GlobalScope`.
- [x] `tests/unit/models/test_user_serialization.py` — round-trip asserts `kind`.
- [x] `tests/unit/v1/test_carbon_report_module.py` — builders migrated.
- [x] `tests/unit/v1/test_travel_table_visibility.py` — builders migrated.
- [x] Also: `tests/unit/v1/test_carbon_report.py` status tests patch the new
      `require_module_unit_scope`; `test_year_configuration_list.py`
      `fake_is_permitted` → `backoffice.configuration`; `test_csv_upload_e2e.py`
      `GlobalScope()`.
- [x] **Full `uv run pytest`: 1861 passed, 1 failed.** The lone failure
      (`test_stats_json_pg::…_scope3`, a stats-math assertion) is **pre-existing
      and unrelated** — diff vs `dev` touches no stats code; not a 403/scope issue.

### TODO — frontend (covers #862 + this redesign)

- [x] `frontend/src/constant/permissions.ts` — added `backoffice.configuration`,
      `backoffice.pipeline_operations`, `backoffice.logs`, `backoffice.ui_texts`;
      removed `system.users`; `data_management` already gone. Nested
      `BackOfficePermissions` updated too.
- [x] `frontend/src/utils/permission.ts` — `hasAnyScopePermission` already matches
      `modules.<m>/<unit>/own` (prefix); added `hasUnitScopePermission` (matches
      bare/`<unit>` but **not** `/own`) for unit-level controls; dropped the
      removed `system.*` branch in `hasBackOfficeAreaPermission`.
- [x] `frontend/src/router/routes.ts` — per-page guards fixed: pipeline-operations
      → `backoffice.pipeline_operations`, ui-texts → `backoffice.ui_texts`, logs →
      `backoffice.logs`, back-office redirect `backoffice.*` → `backoffice.reporting`,
      doc-view → `backoffice.documentation`. Also fixed `auth.ts` `hasUserPermission`
      to match the `/own` key (std keep module CRUD); added store
      `hasUserUnitScopePermission`.
- [x] Regenerated `frontend/src/types/api/openapi.d.ts` (from live backend);
      scrubbed `system.users` backend docstrings first → 0 `system.users` left.
- [x] `make type-check` (vue-tsc) **green**.

### TODO — docs

- [x] `docs/src/backend/06-PERMISSION-SYSTEM.md` — matrix rebuilt to the
      page-driven keys + explicit scope; std `/own` key shape, affiliation
      `(A)` reporting, and the unit-level module `status` gate documented; API
      shape JSON + role/scope text refreshed; removed the stale `data_management`
      / `system.users` rows and the obsolete "in flight" note. `mkdocs --strict` green.
- [ ] Flip this plan's frontmatter `status` to `delivered` and fill `issue:` once
      an issue exists.

### Verify (final)

```bash
cd backend && uv run pytest -q
cd frontend && make type-check
cd docs && npx prettier --check src/**/*.md && uv run mkdocs build --strict
```
