---
status: delivered
last_updated: 2026-05-05
summary: Step-by-step recipe for adding a new permission end-to-end.
---

# How to add a new permission

## 1. Declare it in `app/utils/permissions.py`

Add the new key to the structure returned by `initialize_permissions()`,
then grant it from the relevant role mappers:

```python
def initialize_permissions() -> dict:
    return {
        "backoffice": {
            "users": {"view": False, "edit": False},
            "your_new_resource": {"view": False, "edit": False},  # ADD
        },
        "modules": {
            "headcount": {"view": False, "edit": False},
        },
    }

def map_role_permissions(role: str) -> dict:
    permissions = initialize_permissions()
    if role == "co2.superadmin":
        permissions["backoffice"]["your_new_resource"]["view"] = True
        permissions["backoffice"]["your_new_resource"]["edit"] = True
    return permissions
```

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
  permissions, "backoffice.your_new_resource", "edit",
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
