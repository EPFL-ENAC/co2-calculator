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
try-catch can handle the error.

### Call Chain

```
ModuleTable.vue onMounted
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
accessed. No route-guard hacks, no `skipForbiddenRedirect`.

| User type                                | Result                         |
| ---------------------------------------- | ------------------------------ |
| Principal for THIS unit / global role    | 200, full member list          |
| `CO2_USER_STD` for this unit             | 200, own record only           |
| Principal of a **different** unit        | 200, own record only           |
| Neither `headcount.view` nor travel perm | 403                            |
| Standard user not found in headcount     | 200, empty list + hint message |

The critical detail: `get_module_permission_decision` calls
`calculate_user_permissions`, which is **scope-blind** — a principal for unit A
gets `modules.headcount.view = True` regardless of which unit they are accessing.
The data filter must therefore use `pick_role_for_institutional_id` (from
`app.core.role_priority`) to resolve the user's effective role **for the
specific unit_id in the request**, not globally.

---

### Part 1 — Backend: unit-scoped permission gate + data filter

**File**: `backend/app/api/v1/carbon_report_module.py`

Imports added:

```python
from app.core.role_priority import pick_role_for_institutional_id
from app.models.unit import Unit
from app.models.user import GlobalScope, RoleName
```

Logic in `list_headcount_members`:

```python
# Gate: allow if user has professional_travel.view OR headcount.view OR is global
travel_decision = await get_module_permission_decision(current_user, "professional-travel", "view")
headcount_decision = await get_module_permission_decision(current_user, "headcount", "view")
is_global = any(isinstance(r.on, GlobalScope) for r in current_user.roles)
if not (is_global or headcount_decision.get("allow") or travel_decision.get("allow")):
    raise HTTPException(status_code=403, detail="...")

# Data scope: resolve user's effective role for THIS unit specifically
unit = await db.get(Unit, unit_id)
unit_iid = unit.institutional_id if unit else None

has_full_access = (
    headcount_decision.get("allow", False)
    or any(isinstance(r.on, GlobalScope) for r in current_user.roles)
    or (
        unit_iid is not None
        and pick_role_for_institutional_id(current_user.roles, unit_iid)
        == RoleName.CO2_USER_PRINCIPAL
    )
)

# Single fetch; filter in Python — get_headcount_members returns list[dict]
rows = await DataEntryService(db).get_headcount_members(
    carbon_report_module_id=carbon_report_module_id,
)
if not has_full_access:
    user_iid = current_user.institutional_id
    rows = [r for r in rows if r.get("institutional_id") == user_iid]
return [HeadcountMemberDropdownItem(**row) for row in rows]
```

---

### Part 2 — Frontend: HeadcountMemberSelect component

**File**: `frontend/src/components/organisms/module/HeadcountMemberSelect.vue`

The component is the sole owner of the traveler dropdown UX. It handles three
states after the API call resolves:

| State                     | Condition                                                    | UX                                         |
| ------------------------- | ------------------------------------------------------------ | ------------------------------------------ |
| Standard user, found      | `members.length === 1 && user.iid === members[0].iid`        | Readonly `q-input`, value auto-emitted     |
| Standard user, not found  | `members.length === 0 && !hasPermission(perms, 'headcount')` | Disabled `q-select` + "not validated" hint |
| Full access, empty list   | `members.length === 0 && hasPermission(perms, 'headcount')`  | Disabled `q-select` + "add members" hint   |
| Full access, list present | `members.length > 0`                                         | Normal `q-select` dropdown                 |

Key implementation details:

- `modelValue` prop and emit type are `string | null` (institutional_id is a string, not a number)
- Quasar Vue 3 readonly display: use `:model-value` (not `:value`) on `q-input`
- Auto-emit on mount when `isStandardUser`: `emit('update:modelValue', options[0].value)` — ensures the parent form receives the value and validation passes
- `isNotValidated` uses `hasPermission(authStore.user?.permissions, 'headcount', 'view')` from `src/utils/permission`

i18n keys (in `frontend/src/i18n/professional_travel.ts`):

- `${MODULES.ProfessionalTravel}-field-traveler-empty-headcount` — shown to managers with no headcount data
- `${MODULES.ProfessionalTravel}-field-traveler-not-validated` — shown to standard users not found in headcount

---

### Part 3 — Tests

**File**: `backend/tests/integration/v1/test_headcount_members_permission.py`

| Scenario                                     | Expected             |
| -------------------------------------------- | -------------------- |
| No relevant permission                       | 403                  |
| Principal for THIS unit                      | 200, all members     |
| STD for this unit                            | 200, own record only |
| Principal for OTHER unit + STD for this unit | 200, own record only |
| Global role (superadmin)                     | 200, all members     |
| Travel user not in headcount data            | 200, empty list      |

---

## Alternatives Considered and Rejected

### A. `skipForbiddenRedirect` flag on the API call

Pass a flag through ky's `context` so the 403 interceptor skips the redirect for
this specific call, then handle the empty state gracefully in the component.

**Rejected**: Degrades the UX — User Standard would see an empty, unusable
dropdown. The user must see themselves as the traveler to submit a valid entry.
Route-guard hacks also mask the real problem (backend was too narrow).

### B. Simple OR-check only (no data filtering)

Allow any user with `headcount.view` OR `professional_travel.view` to see all
members.

**Rejected**: User Standard would gain read access to other people's headcount
records — data leakage.

### C. New dedicated endpoint under professional-travel

Create `GET /{unit_id}/{year}/professional-travel/travelers` with travel-only
permissions.

**Rejected**: Duplicates logic. The existing endpoint was designed for this
purpose and already supports the scoping we need.

---

## Files Changed

| File                                                                 | Change                                                                                                |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py`                         | Unit-scoped gate (OR travel/headcount/global) + single-fetch Python filter                            |
| `frontend/src/components/organisms/module/HeadcountMemberSelect.vue` | `isStandardUser` readonly + auto-emit; `isNotValidated` hint; type fix `string\|null`; `:model-value` |
| `frontend/src/i18n/professional_travel.ts`                           | New key `field-traveler-not-validated` (EN + FR)                                                      |
| `backend/tests/integration/v1/test_headcount_members_permission.py`  | 6 scenarios covering gate, data scoping, and role priority conflict                                   |
