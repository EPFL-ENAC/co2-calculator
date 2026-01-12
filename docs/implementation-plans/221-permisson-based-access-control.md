# Permissions-Based Access Control Implementation

## Overview

Implement fine-grained, permission-based access control using a **Hybrid Approach** (Defense in Depth):

- **Route-Level Authorization**: Coarse-grained "Guard at the Gate"
- **Service-Level Authorization**: Fine-grained "Guard at the Vault" with row-level security
- **Frontend Permissions**: UX-driven display logic (backend-driven, not security)

---

## Phase 1: Backend Permission Infrastructure

### 1.1 Create Permission Dependency (OPA Pattern)

**Update policy module** (`backend/app/core/policy.py`)

- [x] Extend `query_policy()` function to support permission checks
  - Add routing for `"authz/permission/check"` policy path
  - Create `_evaluate_permission_policy()` helper function
  - Use EXISTING `has_permission()` utility from `app.utils.permissions`
  - Return policy decision dict: `{"allow": bool, "reason": str}`

**Add permission dependency** (`backend/app/core/security.py`)

- [x] Create dependency factory function `require_permission(path: str, action: str = "view")`
  - Returns a FastAPI dependency that checks permissions using OPA pattern
  - Follows the same pattern as `resource_service.py`:
    1. Build OPA input with user context: `{"user": {...}, "path": path, "action": action}`
    2. Query policy: `decision = await query_policy("authz/permission/check", input_data)`
    3. Check decision: `if not decision.get("allow"): raise HTTPException(403)`
    4. Return authenticated user if permission granted
  - Usage: `user: User = Depends(require_permission("modules.headcount", "edit"))`
  - Log permission checks for audit trail

**Implementation details:**

- [x] Create `_build_permission_input(user, path, action)` helper
  - Similar to `_build_opa_input()` in `resource_service.py`
  - Include user ID, email, roles, and permissions
- [x] Include logging similar to resource_service pattern

**Security Considerations:**

- [x] **404 vs 403 responses**: Return `404 Not Found` for resources the user doesn't own (not `403 Forbidden`) to prevent enumeration attacks

### 1.2 Implement Data Filtering Service (OPA Pattern)

**Extend policy module** (`backend/app/core/policy.py`)

- [x] Add data filtering policy evaluation
  - Create `_evaluate_data_filter_policy()` function
  - Support policies: `"authz/data/list"`, `"authz/data/access"`
  - Return filter criteria based on user's role scope
  - Return `{"allow": bool, "filters": {"unit_ids": [...], "user_id": ...}}`

**Create service layer with context injection pattern**

Option A: Add to `backend/app/services/authorization_service.py` (new file)
<<<<<<< Updated upstream
Option B: Integrate directly into domain services (e.g., `headcount_service.py`)
=======

> > > > > > > Stashed changes

**Pattern: Context-Injected Services**

```python
class HeadcountService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user  # The "Actor"

    async def list_headcounts(self, skip: int = 0, limit: int = 100):
        # Build OPA input using injected user context
        input_data = {
            "user": {"id": self.user.id, "roles": self.user.roles},
            "resource_type": "headcount",
            "action": "list"
        }

        # Query policy for data filters
        decision = await query_policy("authz/data/list", input_data)
        filters = decision.get("filters", {})

        # Pass filters to repository
        return await headcount_repo.get_headcounts(self.db, filters=filters, skip=skip, limit=limit)
```

**Route integration:**

```python
@router.get("/headcounts")
async def list_headcounts(
    user: User = Depends(require_permission("modules.headcount", "view")),
    db: AsyncSession = Depends(get_db)
):
    service = HeadcountService(db, user=user)
    return await service.list_headcounts()
```

**Key helpers to implement:**

- [x] `_build_data_filter_input(user: User, resource_type: str, action: str) -> dict`
- [x] `_build_resource_access_input(user: User, resource_type: str, resource: dict) -> dict`

### 1.3 Update Repository Layer (Filter-Based)

**Update repositories to accept filter dictionaries**

- [x] `backend/app/repositories/headcount_repo.py`
  - Update list methods to accept optional `filters: dict` parameter
  - Apply filters to query: `if "unit_ids" in filters: query = query.where(Headcount.unit_id.in_(filters["unit_ids"]))`
  - Apply user filter: `if "user_id" in filters: query = query.where(Headcount.created_by == filters["user_id"])`

- [x] `backend/app/repositories/professional_travel_repo.py`
  - Update to accept `filters: dict` parameter
  - Apply unit filter and user filter
  - Keep existing location search, sorting, pagination logic

- [ ] Other module repositories
  - Update to accept `filters: dict` parameter
  - Apply standard filter patterns

**Filter dictionary structure:**

```python
filters = {
    "unit_ids": ["ENAC", "STI"],  # Empty list = no filter
    "user_id": "user-123",         # None = no filter
    "scope": "global" | "unit" | "own"  # For logging/debugging
}
```

### 1.4 Update `/auth/me` Endpoint

**File: `backend/app/api/v1/auth.py`**

- [x] Update `/auth/me` endpoint to return calculated permissions

  ```python
  from app.utils.permissions import calculate_user_permissions

  @router.get("/me")
  async def me(user: User = Depends(get_current_active_user)):
      return {
          "id": user.id,
          "email": user.email,
          "display_name": user.display_name,
          "roles_raw": user.roles_raw,
          "permissions": calculate_user_permissions(user.roles)  # ADD THIS
      }
  ```

---

## Phase 2: Backend Route Protection

### 2.1 Update Backoffice Routes

**File: `backend/app/api/v1/backoffice.py`**

- [x] `GET /backoffice/users` → `require_permission("backoffice.users", "view")`
- [x] `POST /backoffice/users` → `require_permission("backoffice.users", "edit")`
- [x] `PUT /backoffice/users/{id}` → `require_permission("backoffice.users", "edit")`
- [x] `DELETE /backoffice/users/{id}` → `require_permission("backoffice.users", "edit")`
- [x] `POST /backoffice/users/export` → `require_permission("backoffice.users", "export")`

- [x] Create or update UserService with context injection
- [x] Implement policy-based filtering in `list_users()`
- [x] Return 404 (not 403) in `get_user()` if user lacks access

### 2.2 Update Module Routes

**File: `backend/app/api/v1/headcounts.py`**

- [x] Add route-level guards:
  - GET → `require_permission("modules.headcount", "view")`
  - POST/PUT/DELETE → `require_permission("modules.headcount", "edit")`

- [x] Create `HeadcountService` with context injection
- [x] Update routes to use service with policy-based filtering

**File: `backend/app/api/v1/modules.py`**

- [x] Professional Travel → `require_permission("modules.professional_travel", "view/edit")`
- [x] Equipment → `require_permission("modules.equipment", "view/edit")`
- [x] Infrastructure → `require_permission("modules.infrastructure", "view/edit")`
- [x] Purchase → `require_permission("modules.purchase", "view/edit")`
- [x] Internal Services → `require_permission("modules.internal_services", "view/edit")`
- [x] External Cloud → `require_permission("modules.external_cloud", "view/edit")`

**Special case for Professional Travel**:

- Policy should return `{"filters": {"user_id": user.id}}` for standard users

**File: `backend/app/api/v1/units.py`**

- [x] Add guards to unit management endpoints
- [x] Service-level filtering based on user's scope (global/affiliation/unit)

---

## Phase 3: Frontend UI Component Updates

### 3.1 Module Tables

**Pattern to apply**:

```vue
<script setup>
import { computed } from "vue";
import { useAuthStore } from "src/stores/auth";
import { hasPermission } from "src/utils/permission";

const authStore = useAuthStore();
const canEdit = computed(() =>
  hasPermission(authStore.user?.permissions, "modules.headcount", "edit"),
);
</script>

<template>
  <q-btn v-if="canEdit" label="Add New" @click="addNew" />
  <q-badge v-else color="warning">View Only</q-badge>
</template>
```

**Components to update**:

- [x] Headcount table component
- [x] Equipment table component
- [ ] Professional travel table component
- [ ] All other module table components

**Requirements**:

- [x] Hide "Add New" button if user lacks edit permission
- [x] Disable/hide edit and delete buttons if user lacks edit permission
- [x] Show "View Only" badge for read-only users

### 3.2 Enhanced Error Handling

**Create error utilities** (`frontend/src/utils/errors.ts` - NEW FILE)

- [x] `parsePermissionError(error)` - Extract permission details from 403 response
- [x] `showPermissionError(error)` - Display user-friendly permission error toast

**Enhance unauthorized page** (`frontend/src/pages/ErrorUnauthorized.vue`)

**Update API interceptor** (`frontend/src/api/http.ts`)

- [x] Parse error response body for permission details
- [x] Show Quasar toast notification before redirecting
- [x] Pass permission details to unauthorized page via query params

---

## Phase 4: Error Messages

### 4.1 Create Custom Exception Classes

**File: `backend/app/core/exceptions.py`** (NEW FILE)

- [ ] `class PermissionDeniedError(Exception)` with `required_permission`, `action`, `message`
- [ ] `class InsufficientScopeError(PermissionDeniedError)` for scope-related denials
- [ ] `class RecordAccessDeniedError(PermissionDeniedError)` for record-level denials

### 4.2 Implement Error Handlers

**File: `backend/app/core/exception_handlers.py`** (NEW FILE)

- [ ] `permission_denied_handler(request, exc: PermissionDeniedError)`
  - Returns HTTP 403 with clear message format
- [ ] Register handlers in `backend/app/main.py`

---

# Phase 5: Backend Refactoring (Role Removal)

## 5.1 Security & Utilities

- [ ] **Cleanup:** Delete `require_role` and `RoleChecker` from `security.py`.
- [ ] **Deprecation:** Mark `has_role()` as deprecated; redirect callers to `has_permission()`.
- [ ] **OPA Context:** Update input builders to calculate `user.permissions` from `roles_raw`.

## 5.2 Route Guards

- [ ] **Backoffice:** Replace `admin` checks with `require_permission("backoffice.users", "view/edit")`.
- [ ] **Modules:** Map `standard` role logic to `require_permission("modules.[name]", "edit")`.
- [ ] **Units:** Replace `unit_admin` guards with `require_permission("units", "manage")`.

## 5.3 Service Logic

- [ ] **Data Filtering:** Replace `if "admin" in user.roles` with `get_data_filters(user, resource, action)`.
- [ ] **Abstraction:** Services must depend on permission-based filters, not raw role strings.

---

## Phase 6: Documentation

### 6.1 API Documentation

**Update OpenAPI schema** (`backend/app/main.py`)

- [x] Add permission requirements to endpoint descriptions
- [x] Document 403 error responses with examples

### 6.2 Developer Guide

**Create** (`docs/developers/permissions.md` - NEW FILE)

- [x] How to add new permissions
- [x] How to use `require_permission()` decorator
- [x] How to implement data filtering in services
- [x] How to add permission checks in frontend components
- [x] Testing permission-based features
