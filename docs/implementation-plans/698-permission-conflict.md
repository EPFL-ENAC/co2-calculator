# Fix: Permission Conflict in Professional Travel (Issue #698)

## Problem

A "User Standard" with `professional_travel.edit` permission is redirected to the
Unauthorized page when clicking on Professional Travel.

### Root Cause (two layers)

**Layer 1 — Backend permission too narrow**:
When `ModuleTable.vue` mounts for Professional Travel, it calls
`getHeadcountMembers()` (line 1496) to populate the traveler name dropdown.
This hits `GET /modules/{unit_id}/{year}/headcount/members`, which checked:

```python
await _check_module_permission(current_user, "headcount", "view")
```

User Standard does not have `headcount.view`, so the backend returned 403.

**Layer 2 — Frontend 403 interceptor too aggressive**:
The global HTTP interceptor (`frontend/src/api/http.ts`) catches **every** 403
and does `location.replace('/unauthorized')`. This fires before the component's
try-catch (`ModuleTable.vue:1503`) can handle the error — even a non-critical
background dropdown fetch blows the user off the page.

### Call Chain

```
ModuleTable.vue onMounted (line 1490)
  -> getHeadcountMembers(unitId, year)
  -> GET /modules/{unit}/{year}/headcount/members
  -> _check_module_permission(user, "headcount", "view")  -- FAILS (403)
  -> http.ts afterResponse hook intercepts 403 BEFORE try-catch runs
  -> location.replace("/unauthorized")
```

---

## Solution

### Design: protect the data, not just the endpoint

The fix applies data-level access control scoped to the specific unit being
accessed, as recommended by `@charlottegiseleweil` and `@ymarcon`:

- Principal for THIS unit / global role → full member list
- `CO2_USER_STD` for this unit (or principal of a different unit) → own record only
- Neither permission → 403

The critical detail: `get_module_permission_decision` calls
`calculate_user_permissions`, which is **scope-blind** — a principal for unit A
gets `modules.headcount.view = True` regardless of which unit they are accessing.
The data filter must therefore use `pick_role_for_institutional_id` (from
`app.core.role_priority`) to resolve the user's effective role **for the
specific unit_id in the request**, not globally.

---

### Part 1 — Backend: unit-scoped permission gate + data filter

**File**: `backend/app/api/v1/carbon_report_module.py`

New imports:

```python
from app.core.role_priority import pick_role_for_institutional_id
from app.models.unit import Unit
from app.models.user import GlobalScope, RoleName
```

Replacement logic in `list_headcount_members`:

```python
# Gate: allow if user has professional_travel.view OR headcount.view
travel_decision = await get_module_permission_decision(current_user, "professional-travel", "view")
headcount_decision = await get_module_permission_decision(current_user, "headcount", "view")
if not (headcount_decision.get("allow") or travel_decision.get("allow")):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permission denied: headcount.view or professional_travel.view required",
    )

# Data scope: resolve user's effective role for THIS unit specifically
unit = await db.get(Unit, unit_id)
unit_iid = unit.institutional_id if unit else None

has_full_access = (
    any(isinstance(r.on, GlobalScope) for r in current_user.roles)
    or (
        unit_iid is not None
        and pick_role_for_institutional_id(current_user.roles, unit_iid)
        == RoleName.CO2_USER_PRINCIPAL
    )
)

rows = await DataEntryService(db).get_headcount_members(carbon_report_module_id=...)
all_members = [HeadcountMemberDropdownItem(**row) for row in rows]

if not has_full_access:
    return [m for m in all_members if m.institutional_id == current_user.institutional_id]
return all_members
```

---

### Part 2 — Frontend: allow non-critical fetches to skip the 403 redirect

Use ky's built-in `context` property (`Record<string, unknown>`) — no type cast
needed.

**File**: `frontend/src/api/http.ts`

```typescript
if (res.status === 403) {
  if (options.context?.skipForbiddenRedirect === true) return;
  // ... existing redirect logic unchanged ...
}
```

**File**: `frontend/src/api/modules.ts`

```typescript
return api
  .get(`modules/${unitEncoded}/${yearEncoded}/headcount/members`, {
    context: { skipForbiddenRedirect: true },
  })
  .json<HeadcountMemberDropdownItem[]>();
```

---

### Part 3 — Tests

**File**: `backend/tests/integration/v1/test_headcount_members_permission.py`

| Scenario                                     | Expected                                 |
| -------------------------------------------- | ---------------------------------------- |
| No relevant permission                       | 403                                      |
| Principal for THIS unit                      | 200, all members                         |
| STD for this unit                            | 200, own record only                     |
| Principal for OTHER unit + STD for this unit | 200, own record only (role priority fix) |
| Global role (superadmin)                     | 200, all members                         |
| Travel user not in headcount data            | 200, empty list                          |

---

## Alternatives Considered

### A. Simple OR-check only (no data filtering)

Allow any user with `headcount.view` OR `professional_travel.view` to see all members.

**Rejected**: User Standard would gain read access to other people's headcount records.

### B. New dedicated endpoint under professional-travel

Create `GET /{unit_id}/{year}/professional-travel/travelers` with travel-only permissions.

**Rejected**: Duplicates logic. The existing endpoint was designed for this purpose.

### C. Frontend graceful degradation only

Skip the 403 redirect, leave the dropdown empty.

**Rejected**: User Standard needs to see themselves in the dropdown to correctly
fill in their own travel entries.

---

## Files Changed

| File                                                                | Change                                                                                         |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py`                        | Unit-scoped permission gate + data-level filter using `pick_role_for_institutional_id`         |
| `frontend/src/api/http.ts`                                          | Check `options.context.skipForbiddenRedirect` before 403 redirect (type-safe via ky `context`) |
| `frontend/src/api/modules.ts`                                       | Pass `context: { skipForbiddenRedirect: true }` on headcount members call                      |
| `backend/tests/integration/v1/test_headcount_members_permission.py` | 6 scenarios covering access gate, data scoping, and role priority conflict                     |
