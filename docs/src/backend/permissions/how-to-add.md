---
status: delivered
last_updated: 2026-05-05
summary: Step-by-step recipe for adding a new permission end-to-end.
---

# How to add a new permission

## 1. Grant it in `app/models/user.py::calculate_user_permissions`

Permissions are computed dynamically from a user's roles by
[`calculate_user_permissions`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/models/user.py).
The returned object is a **flat** dict keyed by dot-notation paths, with a
list of action strings as the value (e.g.
`{"backoffice.users": ["view", "edit", "export"]}`). To introduce a new
permission, add the key under the appropriate `RoleName.*` branch:

```python
# inside calculate_user_permissions(...)
elif role_name == RoleName.CO2_SUPERADMIN.value:
    if is_global_scope(scope):
        # ... existing grants ...
        permissions["backoffice.your_new_resource"] = merge_actions(
            permissions.get("backoffice.your_new_resource"),
            ["view", "edit"],
        )
```

Module permissions are unit-scoped — append `scope_key` to the path so the
key looks like `modules.your_new_resource/<institutional_id>`:

```python
elif role_name == RoleName.CO2_USER_PRINCIPAL.value:
    if is_role_scope(scope):
        permissions[f"modules.your_new_resource{scope_key}"] = merge_actions(
            permissions.get(f"modules.your_new_resource{scope_key}"),
            ["view", "edit", "sync"],
        )
```

There is no separate "registry" of permission keys — adding the key to a
role branch IS the declaration. The runtime check helper
[`app/utils/permissions.py::has_permission`](https://github.com/EPFL-ENAC/co2-calculator/blob/main/backend/app/utils/permissions.py)
reads the resulting dict; no changes needed there unless you introduce a
new scope shape.

## 2. Protect the route

```python
from app.core.security import require_permission
from app.models.user import User

@router.get(
    "/your-endpoint",
    responses={403: {"description": "Permission denied"}},
)
async def get_your_resource(
    current_user: User = Depends(
        require_permission("backoffice.your_new_resource", "view")
    ),
):
    """Required permission: ``backoffice.your_new_resource.view``."""
    ...
```

`require_permission` raises `HTTPException(403, detail="Permission denied")`
on failure — the missing `path.action` is **not** echoed back to the
client, but is recorded in the `permission_check` log entry (see
[audit](./audit.md)).

## 3. Filter data in the service (list endpoints)

```python
from app.services.authorization_service import get_data_filters

filters = await get_data_filters(
    user=self.user, resource_type="your_new_resource", action="list"
)
return await self.repository.get_all(filters=filters)
```

## 4. Add a resource-level rule (only if needed)

Extend `_evaluate_resource_access_policy()` in `app/core/policy.py`:

```python
if resource_type == "your_new_resource":
    if some_business_rule:
        return {"allow": False, "reason": "..."}
    return {"allow": True, "reason": "Owner access"}
```

## 5. Update the frontend

```typescript
const canEdit = hasPermission(
  permissions,
  "backoffice.your_new_resource",
  "edit",
);
```

Use `canEdit` for conditional rendering or to disable buttons. Backend
`require_permission` remains the source of truth — frontend gating is UX
only.

## 6. Test it

- Unit: assert 403 for unauthorised callers, 200 for authorised ones.
- Integration: verify scope filtering with `standard / principal /
superadmin` fixtures.
- Update the [matrix](./matrix.md) row for the new permission.

## 7. Document and ship

Update [matrix](./matrix.md), the route docstring, and any changelog/ADR.
Mention scope intent (global / unit / own) so reviewers can match the new
grant against issue #459's sub-perimeter scoping work.
