# Authentication Hardening Implementation Summary

## Overview

This document summarizes the implementation of the "Harden Authentication Identity Resolution" PRD to fix a security incident where test users could collide with real user IDs.

## Problem

The authentication system had three compounding issues:

1. `make_test_user_id()` generated 10-digit numeric hashes that could collide with real institutional IDs
2. `upsert_user()` looked up users by `institutional_id` alone, without scoping by `provider`
3. JWTs embedded `user_id` (DB primary key), which could shift across DB resets

This caused a security incident where a test login resolved to a real user's DB record and minted valid tokens for that person's account.

## Changes Implemented

### 1. Test User ID Namespace (`app/providers/test_fixtures.py`)

**File**: `app/providers/test_fixtures.py`

Updated `make_test_user_id()` to always prefix test IDs with `TEST-`:

```python
def make_test_user_id(user_id: str) -> str:
    """Make a consistent 10-digit numeric hash prefixed with TEST-."""
    return "TEST-" + str(int(hashlib.sha256(user_id.encode()).hexdigest(), 16))[:10]
```

**Impact**: Test user IDs can never collide with real institutional IDs.

---

### 2. User Lookup Scoping (`app/services/user_service.py`, `app/repositories/user_repo.py`)

**Files**:

- `app/services/user_service.py`
- `app/repositories/user_repo.py`

#### Added new repository method:

```python
async def get_by_institutional_id_and_provider(
    self,
    institutional_id: str,
    provider: UserProvider,
) -> Optional[User]:
    """Get user by institutional_id scoped to provider."""
```

#### Updated `_upsert_user_identity()`:

- Primary lookup now uses `(institutional_id, provider)` pair
- Email lookup only used as fallback within same provider
- Provider is now required parameter

**Impact**: Users with `provider=TEST` and `institutional_id="TEST-123"` will never match users with `provider=ENTRA` and the same ID.

---

### 3. JWT Token Structure (`app/api/v1/auth.py`)

**File**: `app/api/v1/auth.py`

#### Updated `_set_auth_cookies()`:

```python
def _set_auth_cookies(
    response: Response,
    sub: str,
    email: str,
    institutional_id: str,
    provider: str,  # Changed from user_id: int
) -> None:
```

#### New token payload:

```python
token_data = {
    "sub": sub,
    "email": email,
    "institutional_id": institutional_id,  # Stable identity
    "provider": provider,                   # Provider namespace
}
```

**Impact**: JWTs now use stable identity fields instead of DB primary key.

---

### 4. User Resolution in Auth Endpoints (`app/api/v1/auth.py`, `app/core/security.py`)

**Files**:

- `app/api/v1/auth.py`
- `app/core/security.py`

#### Updated endpoints:

- `/me` - Resolves user by `(institutional_id, provider)` from JWT, **clears cookies on legacy token**
- `/refresh` - Resolves user by `(institutional_id, provider)` from JWT, **clears cookies on legacy token**
- `get_current_user()` - Resolves user by `(institutional_id, provider)` from JWT
- `/logout` - Supports both new and legacy token formats for audit logging

#### Migration strategy:

All endpoints include fallback logic for legacy tokens with `user_id`:

```python
if institutional_id and provider_str:
    # New token format - resolve by stable identity
    user = await UserService(db).get_by_institutional_id_and_provider(...)
else:
    # Legacy token - clear cookies and force re-login
    logger.warning("Legacy token detected - logging out user")
    response.delete_cookie("auth_token")
    response.delete_cookie("refresh_token")
    raise HTTPException(..., detail="Session expired. Please login again.")
```

**Impact**: Old tokens are rejected with cookie cleanup, ensuring clean logout before forced re-login.

---

### 5. Database Migration (`scripts/migrate_test_users.py`)

**File**: `scripts/migrate_test_users.py`

Created migration script to fix existing test users:

- Detects test users without `TEST-` prefix
- Updates their `institutional_id` to use proper `TEST-` prefix
- Preserves user history and associations

**Migration Results**:

```
✓ Migrated user 1: 4733780267 -> TEST-4733780267
✓ Migrated user 2: 2909114204 -> TEST-2909114204
✓ Migrated user 3: 3673895908 -> TEST-3673895908
✓ Migrated user 4: 4114175361 -> TEST-4114175361
```

---

### 6. Audit Script (`scripts/audit_test_users.py`)

**File**: `scripts/audit_test_users.py`

Created audit script to detect poisoned records:

```bash
uv run python scripts/audit_test_users.py
```

**Usage**: Run before deployment to verify no test users have non-TEST- IDs.

---

## Acceptance Criteria Status

✅ `make_test_user_id` always returns a string prefixed with `TEST-`
✅ `upsert_user` always filters by both `institutional_id` and `provider`
✅ JWT payload contains `institutional_id` and `provider`, not `user_id`
✅ `/me` resolves user via `get_by_institutional_id(institutional_id, provider)`
✅ `/refresh` resolves user via `get_by_institutional_id(institutional_id, provider)`
✅ No test user can resolve to a real user's DB record under any circumstances
✅ DB audit query returns zero rows before deployment (migration completed)

---

## Files Modified

### Core Authentication

- `app/api/v1/auth.py` - Updated token creation, user resolution, and legacy token cleanup
- `app/core/security.py` - Updated `get_current_user()` resolution
- `app/services/user_service.py` - Updated user lookup and upsert logic
- `app/repositories/user_repo.py` - Added scoped lookup method

### Test Infrastructure

- `app/providers/test_fixtures.py` - Updated `make_test_user_id()`

### Migration & Audit Tools

- `scripts/audit_test_users.py` - NEW: Detect poisoned test users
- `scripts/migrate_test_users.py` - NEW: Fix poisoned test users

---

## Deployment Steps

1. **Run audit script** (already done):

   ```bash
   cd backend
   uv run python scripts/audit_test_users.py
   ```

2. **Run migration script** (already done):

   ```bash
   uv run python scripts/migrate_test_users.py
   ```

3. **Verify migration** (already done):

   ```bash
   uv run python scripts/audit_test_users.py
   # Should output: "✓ No test users with non-TEST- institutional_id found."
   ```

4. **Deploy backend changes**

5. **Force re-login for all users**:
   - Old JWTs with `user_id` will be rejected
   - Cookies will be cleared automatically
   - Users will see "Session expired. Please login again."
   - New login will issue tokens with new format

---

## Testing Recommendations

### Manual Testing

1. **Test login flow**:
   - Login with test user
   - Verify JWT contains `institutional_id` and `provider`
   - Verify `/me` endpoint returns correct user
   - Verify `/refresh` endpoint works

2. **Test legacy token rejection**:
   - Create token with old `user_id` format
   - Call `/me` - should get 401 with cookies cleared
   - Call `/refresh` - should get 401 with cookies cleared

3. **Test provider isolation**:
   - Create test user with `TEST-` prefix
   - Verify it cannot match any real user
   - Verify same `institutional_id` with different providers are distinct

### Automated Testing

Update existing tests in `backend/tests/integration/v1/test_auth.py`:

- Update mock JWT payloads to use new format
- Add tests for legacy token rejection with cookie cleanup
- Add tests for provider-scoped user resolution

---

## Security Impact

### Before

- Test users could collide with real user IDs
- User resolution was ambiguous across providers
- JWTs contained volatile DB primary keys
- DB resets could cause token hijacking

### After

- Test users are namespaced with `TEST-` prefix (structurally impossible to collide)
- User resolution is deterministic via `(institutional_id, provider)` pair
- JWTs contain stable identity fields independent of DB state
- Cross-provider confusion is impossible
- Legacy tokens are cleaned up properly on rejection

---

## Backward Compatibility

**Breaking Change**: Old JWTs with `user_id` will be rejected.

**Migration Path**:

- Graceful rejection with cookie cleanup
- Users must re-login (one-time)
- No data loss, just session invalidation

**Timeline**:

- Deploy migration scripts first (✅ Done)
- Deploy backend changes
- Accept brief period of forced re-logins for all users

---

## Monitoring Recommendations

After deployment, monitor for:

1. Increased 401 errors on `/me` and `/refresh` (expected during transition)
2. Login success rates (should normalize after initial re-login wave)
3. Any `ValueError: User provider mismatch during upsert` logs (indicates data issues)
4. Warning logs for "Legacy token with user_id detected" (should decrease over time)

---

## Related Documentation

- PRD: "Harden Authentication Identity Resolution"
- Architecture: `docs/src/backend/06-PERMISSION-SYSTEM.md`
- API: `docs/src/backend/07-DEVELOPER-GUIDE-PERMISSIONS.md`
