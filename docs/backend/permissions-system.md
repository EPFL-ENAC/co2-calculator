# Backend Permission System Architecture

## Overview

The CO2 Calculator uses a **permission-based access control system** that calculates permissions **dynamically on every request** from user roles. The backend returns a `permissions` object in the `/auth/me` endpoint response, which the frontend uses exclusively for access control decisions.

**Key Principles:**

- **Permissions are NEVER stored in the database** - they are calculated on-the-fly from roles
- **Frontend checks permissions, NOT roles** - The backend calculates permissions and provides them ready-to-use
- **Recalculated on every `/auth/me` call** - Always reflects the latest role state

---

## Permission Structure

### Format

Permissions use a **flat structure with dot-notation keys**:

```json
{
  "backoffice.users": {
    "view": true,
    "edit": false,
    "export": false
  },
  "modules.headcount": {
    "view": true,
    "edit": true
  },
  "modules.equipment": {
    "view": true,
    "edit": false
  }
}
```

### Permission Domains

The system has three independent permission domains:

1. **`backoffice.*`** - Administrative features (user management, logs, etc.)
2. **`modules.*`** - CO2 calculation modules (headcount, equipment, etc.)
3. **`system.*`** - System-level routes (reserved for future use)

**Important:** These domains are completely independent. Having a backoffice role does NOT grant module access, and vice versa.

---

## How It Works

### Permission Calculation Flow

```
User makes request to /auth/me
         ↓
Backend reads user from DB (with roles_raw field)
         ↓
User.roles property converts roles_raw to Role objects
         ↓
UserRead schema's @computed_field calls calculate_permissions()
         ↓
calculate_user_permissions() maps roles → permissions
         ↓
Response includes computed permissions (never touches DB)
         ↓
Frontend receives permissions ready to use
```

**Key Points:**

- Permissions are **never read from** or **written to** the database
- Calculation happens in-memory during response serialization
- No additional database queries needed
- Always reflects current role state

---

## Role-to-Permission Mapping

### Backoffice Roles → `backoffice.*` Permissions ONLY

| Role                   | Scope  | Permissions Granted                                  |
| ---------------------- | ------ | ---------------------------------------------------- |
| `co2.backoffice.admin` | Global | `backoffice.users`: {view: ✅, edit: ✅, export: ✅} |
| `co2.backoffice.std`   | Global | `backoffice.users`: {view: ✅, edit: ❌, export: ❌} |

**Backoffice roles provide:**

- Access to user management interface
- Ability to view/edit user accounts
- Ability to export user data
- Access to system logs and audit trails

### User Roles → `modules.*` Permissions ONLY

| Role                 | Scope | Permissions Granted                                                                    |
| -------------------- | ----- | -------------------------------------------------------------------------------------- |
| `co2.user.principal` | Unit  | `modules.headcount`: {view: ✅, edit: ✅}<br>`modules.equipment`: {view: ✅, edit: ✅} |
| `co2.user.std`       | Unit  | `modules.headcount`: {view: ✅, edit: ✅}<br>`modules.equipment`: {view: ✅, edit: ✅} |
| `co2.user.secondary` | Unit  | `modules.headcount`: {view: ✅, edit: ❌}<br>`modules.equipment`: {view: ✅, edit: ❌} |

**User roles provide:**

- Access to CO2 calculation modules for their unit
- Ability to view module data
- Ability to edit module data (principal/std only)
- Read-only access for secondary users

### System Roles → `system.*` Permissions ONLY

| Role              | Scope  | Permissions Granted                   |
| ----------------- | ------ | ------------------------------------- |
| `co2.service.mgr` | Global | _(Reserved for future system routes)_ |

**System roles:**

- Reserved for system-level administrative operations
- Does NOT grant backoffice or module access
- Currently not used (placeholder for future features)

---

## Examples

### Example 1: Backoffice Admin Only

**Roles:**

```json
[
  {
    "role": "co2.backoffice.admin",
    "on": { "scope": "global" }
  }
]
```

**Calculated Permissions:**

```json
{
  "backoffice.users": { "view": true, "edit": true, "export": true },
  "modules.headcount": { "view": false, "edit": false },
  "modules.equipment": { "view": false, "edit": false }
}
```

**Access:**

- ✅ Can manage users in backoffice
- ❌ Cannot access any modules

---

### Example 2: Standard User Only

**Roles:**

```json
[
  {
    "role": "co2.user.std",
    "on": { "unit": "10208" }
  }
]
```

**Calculated Permissions:**

```json
{
  "backoffice.users": { "view": false, "edit": false, "export": false },
  "modules.headcount": { "view": true, "edit": true },
  "modules.equipment": { "view": true, "edit": true }
}
```

**Access:**

- ❌ Cannot access backoffice
- ✅ Can view and edit modules for unit 10208

---

### Example 3: Combined Roles (Backoffice + User)

**Roles:**

```json
[
  {
    "role": "co2.backoffice.std",
    "on": { "scope": "global" }
  },
  {
    "role": "co2.user.principal",
    "on": { "unit": "10208" }
  }
]
```

**Calculated Permissions:**

```json
{
  "backoffice.users": { "view": true, "edit": false, "export": false },
  "modules.headcount": { "view": true, "edit": true },
  "modules.equipment": { "view": true, "edit": true }
}
```

**Access:**

- ✅ Can view users in backoffice (read-only)
- ✅ Can view and edit modules for unit 10208

**This is the key:** Permissions from different domains **combine**!

---

### Example 4: Secondary User (Read-Only)

**Roles:**

```json
[
  {
    "role": "co2.user.secondary",
    "on": { "unit": "10208" }
  }
]
```

**Calculated Permissions:**

```json
{
  "backoffice.users": { "view": false, "edit": false, "export": false },
  "modules.headcount": { "view": true, "edit": false },
  "modules.equipment": { "view": true, "edit": false }
}
```

**Access:**

- ❌ Cannot access backoffice
- ✅ Can view modules (read-only)
- ❌ Cannot edit any data

---

## API Response

### `/auth/me` Endpoint Response

```json
{
  "id": "123456",
  "sciper": 123456,
  "email": "user@epfl.ch",
  "display_name": "John Doe",
  "roles": [
    {
      "role": "co2.user.std",
      "on": { "unit": "10208" }
    }
  ],
  "permissions": {
    "backoffice.users": { "view": false, "edit": false, "export": false },
    "modules.headcount": { "view": true, "edit": true },
    "modules.equipment": { "view": true, "edit": true }
  },
  "is_active": true,
  "created_at": "2025-11-20T11:20:55.590768",
  "updated_at": "2025-11-21T08:05:47.327364",
  "last_login": "2025-11-21T08:05:47.327359"
}
```

**Notes:**

- `roles`: Still included for display purposes only
- `permissions`: **This is what the frontend should use for access control**
- Permissions are **calculated fresh on every `/auth/me` call**
- Permissions are **NOT stored in the database** - they are computed on-the-fly from roles

---

## Implementation Details

### File Structure

```
backend/
├── app/
│   ├── models/
│   │   └── user.py              # User model with calculate_permissions method
│   ├── schemas/
│   │   └── user.py              # UserRead schema with computed permissions field
│   ├── utils/
│   │   └── permissions.py       # Permission calculation logic
│   └── api/
│       └── v1/
│           └── auth.py          # /auth/me endpoint
```

### User Model

**Location:** `backend/app/models/user.py`

```python
class UserBase(SQLModel):
    roles_raw: Optional[List[dict]] = Field(...)

    def calculate_permissions(self) -> dict:
        """Calculate permissions dynamically from roles."""
        from app.utils.permissions import calculate_user_permissions
        return calculate_user_permissions(self.roles)
```

### User Schema

**Location:** `backend/app/schemas/user.py`

```python
class UserRead(UserBase):
    @computed_field
    @property
    def permissions(self) -> dict:
        """Calculate permissions dynamically from roles on every /auth/me call."""
        return self.calculate_permissions()
```

### Permission Calculation

**Location:** `backend/app/utils/permissions.py`

```python
def calculate_user_permissions(roles: List[Role]) -> dict:
    """Calculate permissions based on user roles.

    Returns a flat dict with dot-notation keys:
    {
        "backoffice.users": {"view": bool, "edit": bool, "export": bool},
        "modules.headcount": {"view": bool, "edit": bool},
        "modules.equipment": {"view": bool, "edit": bool}
    }
    """
    permissions = {
        "backoffice.users": {"view": False, "edit": False, "export": False},
        "modules.headcount": {"view": False, "edit": False},
        "modules.equipment": {"view": False, "edit": False},
    }

    for role in roles:
        # Map role to permissions based on role name and scope
        # ...

    return permissions
```

---

## Permission Checking (Backend)

While permissions are primarily for frontend use, the backend can also check them:

```python
from app.utils.permissions import has_permission

# Check if user has permission - calculate on demand
permissions = user.calculate_permissions()
if has_permission(permissions, "modules.headcount", "edit"):
    # Allow editing
    pass

# Or use full path
from app.utils.permissions import get_permission_value

permissions = user.calculate_permissions()
can_edit = get_permission_value(permissions, "modules.headcount.edit")
if can_edit:
    # Allow editing
    pass
```

---

## Key Principles

1. ✅ **Permissions are calculated from roles** - Never check roles in frontend
2. ✅ **Flat structure with dot-notation** - Easy to check and extend
3. ✅ **Independent domains** - Backoffice ≠ Modules ≠ System
4. ✅ **Permissions combine** - Users can have multiple roles across domains
5. ✅ **Backend provides ready-to-use** - Frontend just checks boolean flags
6. ✅ **Fresh on every request** - Permissions recalculated when `/auth/me` is called
7. ✅ **Never stored in DB** - Permissions are computed on-the-fly, not persisted

---

## Migration Notes

### From Role-Based to Permission-Based

**Before (❌ Don't do this):**

```python
# Frontend checking roles
if user.roles.includes('co2.user.std'):
    showModules()
```

**After (✅ Do this):**

```python
# Frontend checking permissions
if user.permissions['modules.headcount'].view:
    showHeadcountModule()
```

### Why Use Computed Permissions?

1. **Always Up-to-Date**: Permissions instantly reflect role changes without syncing DB
2. **No DB Overhead**: No extra columns, indexes, or update queries needed
3. **Flexibility**: Can change role-to-permission mapping without data migration
4. **Granularity**: Fine-grained control (view vs edit vs export)
5. **Simplicity**: Frontend doesn't need to know role hierarchy
6. **Security**: Single source of truth - permissions can't be out of sync with roles
7. **Extensibility**: Easy to add new modules and permissions without touching DB

---

## Troubleshooting

### Permission not appearing in response

**Check:**

1. Role is correctly assigned to user in database (check `roles_raw` field)
2. Role-to-permission mapping exists in `calculate_user_permissions()` function
3. Permission is initialized in the default permissions dict
4. The `@computed_field` decorator is present on the `permissions` property

### User has role but no permission

**Check:**

1. Role scope matches (Global vs RoleScope)
2. Permission calculation logic in `calculate_user_permissions()` handles the role type
3. Role name matches exactly (case-sensitive)
4. The role is being parsed correctly from `roles_raw` to Role objects

### Permission always false

**Check:**

1. User has the correct role in `roles_raw` field
2. Role has correct scope (global for backoffice, unit for modules)
3. Permission calculation in `calculate_user_permissions()` sets the flag to `True` for that role
4. No typos in role name or permission path

### Debugging Tips

**Test permission calculation directly:**

```python
from app.models.user import User

user = User.query.get(user_id)
permissions = user.calculate_permissions()
print(permissions)  # Should show all calculated permissions
```

**Check raw roles:**

```python
user = User.query.get(user_id)
print(user.roles_raw)  # Raw JSON from DB
print(user.roles)      # Parsed Role objects
```

---

## Related Documentation

- Frontend Permission Usage: `docs/frontend/permissions-guide.md` _(to be created)_
- API Reference: `/auth/me` endpoint
- User Model: `backend/app/models/user.py`
- Permission Utils: `backend/app/utils/permissions.py`
