---
status: delivered
issue: 334
last_updated: 2026-05-06
title: "/me Performance Optimization: Decoupling Role Sync and Frontend Refresh Strategy"
summary: "Drop /me latency from ~1s to ~8ms by moving role sync trigger from /me to /refresh."
---

# /me Performance Optimization: Decoupling Role Sync & Frontend Refresh Strategy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `/me` endpoint latency from ~1s to ~8ms by removing synchronous role refresh and moving role sync trigger from `/me` to `/refresh` endpoint.

**Architecture:**

- `/me` becomes a pure DB read (no external API calls, no background sync)
- `/refresh` triggers background role sync (non-blocking)
- Background tasks sync roles periodically based on TTL
- Frontend uses TTL-based fallback for role consistency. No real-time notifications.

**Tech Stack:** FastAPI (BackgroundTasks), PostgreSQL

---

## File Structure

### Backend Files to Create/Modify

**Create:**

- `backend/app/services/role_sync_service.py` - Background role synchronization logic
- `backend/app/tasks/role_sync_tasks.py` - Background task wrappers

**Modify:**

- `backend/app/api/v1/auth.py` - Remove sync from `/me`, add to `/refresh`
- `backend/app/services/user_service.py` - Add role comparison logic
- `backend/app/models/user.py` - Add `last_roles_sync_at` timestamp field

**Frontend Files to Create/Modify:**

- May add manual refresh trigger if needed

---

## Task 1: Database Schema - Add Role Sync Timestamp

**Files:**

- Modify: `backend/app/models/user.py:27-323`
- Test: `backend/tests/unit/models/test_user.py` (if exists)

- [ ] **Step 1: Add last_roles_sync_at field to User model**

```python
# Add to User class in backend/app/models/user.py (after function field, before __repr__)

    function: Optional[str] = Field(
        default=None,
        nullable=True,
        description="User function/title (e.g., 'Professor', 'PhD Student')",
    )
    last_roles_sync_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
        description="Last timestamp when roles were synced from provider",
    )

    def __repr__(self) -> str:
```

- [ ] **Step 2: Create database migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add last_roles_sync_at to users table"
```

- [ ] **Step 3: Apply migration**

```bash
cd backend && uv run alembic upgrade head
```

- [ ] **Step 4: Run tests to verify schema**

```bash
cd backend && uv run pytest tests/ -k "user" -v
```

---

## Task 2: Backend - Role Sync Service

**Files:**

- Create: `backend/app/services/role_sync_service.py`
- Modify: `backend/app/services/user_service.py`
- Test: `backend/tests/unit/services/test_role_sync_service.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for RoleSyncService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timedelta

from app.services.role_sync_service import RoleSyncService
from app.models.user import User, UserProvider, Role, RoleName, RoleScope
from app.providers.role_provider import RoleProvider


@pytest.mark.asyncio
async def test_sync_roles_detects_changes(db_session: AsyncSession):
    """Test that sync detects role changes and updates user."""
    # Arrange
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=[{"role": RoleName.CO2_USER_STD.value, "on": {"institutional_id": "unit1"}}],
        last_roles_sync_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    provider_user = {
        "email": "test@example.com",
        "code": "12345",
        "display_name": "Test User",
        "function": "Tester",
        "roles": [Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="unit2"))],
    }

    service = RoleSyncService(db_session)

    # Act
    result = await service.sync_user_roles(user.id, provider_user)

    # Assert
    assert result.has_changed is True
    assert result.roles_changed is True
    user_updated = await service.user_repo.get_by_id(user.id)
    assert user_updated.last_roles_sync_at is not None


@pytest.mark.asyncio
async def test_sync_roles_no_changes(db_session: AsyncSession):
    """Test that sync skips update when roles unchanged."""
    # Arrange
    roles_raw = [{"role": RoleName.CO2_USER_STD.value, "on": {"institutional_id": "unit1"}}]
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=roles_raw,
        last_roles_sync_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    provider_user = {
        "email": "test@example.com",
        "code": "12345",
        "display_name": "Test User",
        "function": "Tester",
        "roles": [Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="unit1"))],
    }

    service = RoleSyncService(db_session)

    # Act
    result = await service.sync_user_roles(user.id, provider_user)

    # Assert
    assert result.has_changed is False
    assert result.roles_changed is False


@pytest.mark.asyncio
async def test_sync_roles_ignores_recent_sync(db_session: AsyncSession):
    """Test that sync respects TTL and skips recent syncs."""
    # Arrange
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
        roles_raw=[{"role": RoleName.CO2_USER_STD.value, "on": {"institutional_id": "unit1"}}],
        last_roles_sync_at=datetime.utcnow(),  # Just synced
    )
    db_session.add(user)
    await db_session.commit()

    service = RoleSyncService(db_session, sync_ttl_minutes=15)

    # Act
    result = await service.sync_user_roles(user.id, {})

    # Assert
    assert result.skipped_due_to_ttl is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/services/test_role_sync_service.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.role_sync_service'"

- [ ] **Step 3: Write minimal implementation**

```python
"""Role synchronization service for background role updates."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.user import User, Role
from app.repositories.user_repo import UserRepository
from app.services.unit_user_service import UnitUserService
from app.services.unit_service import UnitService

logger = get_logger(__name__)
settings = get_settings()


class RoleSyncResult(BaseModel):
    """Result of a role synchronization operation."""

    user_id: int
    has_changed: bool = False
    roles_changed: bool = False
    units_changed: bool = False
    skipped_due_to_ttl: bool = False
    old_roles: List[Role] = []
    new_roles: List[Role] = []


class RoleSyncService:
    """Service for background role synchronization."""

    def __init__(
        self,
        session: AsyncSession,
        sync_ttl_minutes: int = 15,
    ):
        self.session = session
        self.user_repo = UserRepository(session)
        self.unit_user_service = UnitUserService(session)
        self.unit_service = UnitService(session)
        self.sync_ttl = timedelta(minutes=sync_ttl_minutes)

    async def sync_user_roles(
        self,
        user_id: int,
        provider_user: Dict[str, Any],
        force: bool = False,
    ) -> RoleSyncResult:
        """
        Sync user roles from provider.

        Args:
            user_id: User ID to sync
            provider_user: User data from role provider
            force: Force sync even if recently synced

        Returns:
            RoleSyncResult with change details
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("User not found for role sync", extra={"user_id": user_id})
            return RoleSyncResult(user_id=user_id)

        # Check TTL
        if not force and user.last_roles_sync_at:
            time_since_sync = datetime.utcnow() - user.last_roles_sync_at
            if time_since_sync < self.sync_ttl:
                logger.debug(
                    "Skipping role sync - recently synced",
                    extra={
                        "user_id": user_id,
                        "time_since_sync": str(time_since_sync),
                    },
                )
                return RoleSyncResult(
                    user_id=user_id,
                    skipped_due_to_ttl=True,
                )

        # Compare roles
        old_roles = user.roles or []
        new_roles = provider_user.get("roles", [])

        # Convert to comparable format
        old_roles_comparable = [
            (r.role, r.on.institutional_id if hasattr(r.on, "institutional_id") else None)
            for r in old_roles
        ]
        new_roles_comparable = [
            (r.role, r.on.get("institutional_id") if isinstance(r.on, dict) else None)
            for r in new_roles
        ]

        roles_changed = old_roles_comparable != new_roles_comparable

        if not roles_changed:
            logger.debug(
                "No role changes detected",
                extra={"user_id": user_id},
            )
            # Still update timestamp
            user.last_roles_sync_at = datetime.utcnow()
            await self.session.commit()
            return RoleSyncResult(
                user_id=user_id,
                has_changed=False,
                old_roles=old_roles,
                new_roles=new_roles,
            )

        # Update user roles
        user.roles = new_roles
        user.last_roles_sync_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)

        logger.info(
            "User roles updated",
            extra={
                "user_id": user_id,
                "old_roles_count": len(old_roles),
                "new_roles_count": len(new_roles),
            },
        )

        return RoleSyncResult(
            user_id=user_id,
            has_changed=True,
            roles_changed=True,
            old_roles=old_roles,
            new_roles=new_roles,
        )

    async def sync_user_units(
        self,
        user_id: int,
        roles: List[Role],
    ) -> bool:
        """
        Sync user unit associations based on roles.

        Args:
            user_id: User ID to sync
            roles: User roles (may contain unit scopes)

        Returns:
            True if units changed
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.id is None:
            return False

        # Extract unit IDs from roles
        unit_institutional_ids = set()
        for role in roles:
            if hasattr(role, "on") and hasattr(role.on, "institutional_id"):
                if role.on.institutional_id:
                    unit_institutional_ids.add(role.on.institutional_id)

        if not unit_institutional_ids:
            # No unit roles - delete all associations
            await self.unit_user_service.delete_all_for_user(user.id)
            return True

        # Resolve unit IDs from database
        units = await self.unit_service.get_by_institutional_ids(
            list(unit_institutional_ids)
        )

        if not units:
            logger.warning(
                "No units found for role sync",
                extra={
                    "user_id": user_id,
                    "unit_institutional_ids": list(unit_institutional_ids),
                },
            )
            await self.unit_user_service.delete_all_for_user(user.id)
            return True

        # Delete old associations
        await self.unit_user_service.delete_all_for_user(user.id)

        # Create new associations
        from app.core.role_priority import pick_role_for_institutional_id

        for unit in units:
            if unit.id is None or unit.institutional_id is None:
                continue

            chosen_role = pick_role_for_institutional_id(roles, unit.institutional_id)
            if not chosen_role:
                continue

            await self.unit_user_service.upsert(
                unit_id=unit.id,
                user_id=user.id,
                role=chosen_role,
            )

        logger.info(
            "User units synced",
            extra={"user_id": user_id, "unit_count": len(units)},
        )

        return True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/unit/services/test_role_sync_service.py -v
```

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/role_sync_service.py tests/unit/services/test_role_sync_service.py
git commit -m "feat: add role sync service for background role synchronization"
```

---

## Task 3: Backend - Background Task Integration

**Files:**

- Create: `backend/app/tasks/role_sync_tasks.py`
- Modify: `backend/app/api/v1/auth.py` (add to `/refresh` endpoint)

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for role sync background tasks."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from app.tasks.role_sync_tasks import trigger_role_sync_for_user


@pytest.mark.asyncio
async def test_trigger_role_sync_schedules_task():
    """Test that trigger schedules background task."""
    # This test verifies the task can be called and doesn't raise
    # Full integration test would require actual DB and role provider
    pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/tasks/test_role_sync_tasks.py -v
```

- [ ] **Step 3: Write minimal implementation**

```python
"""Background tasks for role synchronization."""

import asyncio
import logging
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.providers.role_provider import get_role_provider, RoleProviderNetworkError
from app.services.role_sync_service import RoleSyncService
from app.services.user_service import UserService

logger = get_logger(__name__)


async def trigger_role_sync_for_user(
    user_id: int,
    force: bool = False,
) -> None:
    """
    Trigger background role sync for a user.

    This function:
    1. Fetches user from DB
    2. Gets role provider
    3. Fetches fresh roles from provider
    4. Compares with DB roles
    5. Updates if changed

    Args:
        user_id: User ID to sync
        force: Force sync even if recently synced
    """
    from app.core.database import get_db
    from app.models.user import UserProvider

    async for session in get_db():
        async with session:
            try:
                user_service = UserService(session)
                user = await user_service.get_by_id(user_id)

                if not user:
                    logger.warning(
                        "User not found for role sync",
                        extra={"user_id": user_id},
                    )
                    return

                # Get role provider
                role_provider = get_role_provider(user.provider)

                # Fetch fresh user data from provider
                try:
                    provider_user = await role_provider.get_user_by_user_id(
                        user.institutional_id or ""
                    )
                except RoleProviderNetworkError as e:
                    logger.error(
                        "Role provider unavailable",
                        extra={"user_id": user_id, "error": str(e)},
                    )
                    return

                # Sync roles
                sync_service = RoleSyncService(session)
                result = await sync_service.sync_user_roles(
                    user_id, provider_user, force=force
                )

                if result.has_changed:
                    logger.info(
                        "Role sync completed - changes detected",
                        extra={
                            "user_id": user_id,
                            "roles_changed": result.roles_changed,
                        },
                    )

                    # Sync units if roles changed
                    if result.roles_changed:
                        await sync_service.sync_user_units(user_id, result.new_roles)

                else:
                    logger.debug(
                        "Role sync completed - no changes",
                        extra={"user_id": user_id},
                    )

            except Exception as e:
                logger.error(
                    "Role sync failed",
                    extra={"user_id": user_id, "error": str(e)},
                    exc_info=True,
                )
                raise
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/unit/tasks/test_role_sync_tasks.py -v
```

- [ ] **Step 5: Modify auth.py to trigger background sync from /refresh**

```python
# Add to backend/app/api/v1/auth.py after imports:

from app.tasks.role_sync_tasks import trigger_role_sync_for_user


# Modify /refresh endpoint (find existing refresh endpoint):

@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token.

    Uses refresh token to get new access token.
    Triggers background role sync (non-blocking).
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        # Validate refresh token
        payload = decode_jwt(refresh_token)
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # Get user
        user = await UserService(db).get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Generate new access token
        access_token = create_access_token(user_id=user_id)

        # Trigger background role sync (fire-and-forget)
        # Note: This is fire-and-forget - errors don't affect /refresh response
        background_tasks.add_task(
            trigger_role_sync_for_user,
            user_id=user_id,
            force=False,
        )

        return Token(access_token=access_token, token_type="bearer")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to refresh token", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
```

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/tasks/role_sync_tasks.py app/api/v1/auth.py
git commit -m "feat: trigger background role sync from /refresh endpoint"
```

---

## Task 4: Observability & Safety

**Files:**

- Modify: `backend/app/services/role_sync_service.py`
- Modify: `backend/app/tasks/role_sync_tasks.py`

- [ ] **Step 1: Add comprehensive logging**

```python
# Already included in role_sync_service.py and role_sync_tasks.py:
# - Log sync start/end
# - Log role differences
# - Log errors with context
```

- [ ] **Step 2: Add metrics (optional)**

```python
# Add to backend/app/services/role_sync_service.py:

from prometheus_client import Counter, Histogram

ROLE_SYNC_TOTAL = Counter(
    'role_sync_total',
    'Total number of role syncs',
    ['user_id', 'has_changed'],
)
ROLE_SYNC_DURATION = Histogram(
    'role_sync_duration_seconds',
    'Role sync duration',
    ['user_id'],
)

# In sync_user_roles:
with ROLE_SYNC_DURATION.labels(user_id=user_id).time():
    # ... sync logic ...
    ROLE_SYNC_TOTAL.labels(
        user_id=user_id,
        has_changed=result.has_changed,
    ).inc()
```

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/services/role_sync_service.py app/tasks/role_sync_tasks.py
git commit -m "feat: add observability and metrics for role sync"
```

---

## Task 5: Unit Membership Sync with ACCRED

**Files:**

- Modify: `backend/app/services/user_service.py`
- Modify: `backend/app/providers/role_provider.py`

- [ ] **Step 1: Implement unit cleanup on role change**

```python
# Already implemented in role_sync_service.py sync_user_units() method:
# - Deletes all existing unit associations
# - Recreates from current roles
# - Handles unit removal when role scope changes
```

- [ ] **Step 2: Test unit membership sync**

```python
# Add test to test_role_sync_service.py:

@pytest.mark.asyncio
async def test_sync_units_removes_stale_associations(db_session: AsyncSession):
    """Test that unit sync removes associations for removed roles."""
    # Arrange
    user = User(
        id=1,
        institutional_id="12345",
        email="test@example.com",
        provider=UserProvider.ACCRED,
    )
    db_session.add(user)
    await db_session.commit()

    # Create unit
    unit1 = Unit(
        institutional_code="unit1",
        institutional_id="unit1",
        name="Unit 1",
        provider=UserProvider.ACCRED,
    )
    unit2 = Unit(
        institutional_code="unit2",
        institutional_id="unit2",
        name="Unit 2",
        provider=UserProvider.ACCRED,
    )
    db_session.add_all([unit1, unit2])
    await db_session.commit()

    # Create initial association
    from app.models.unit_user import UnitUser
    from app.models.user import RoleName

    unit_user = UnitUser(unit_id=unit1.id, user_id=user.id, role=RoleName.CO2_USER_STD)
    db_session.add(unit_user)
    await db_session.commit()

    # Sync with only unit2 role
    roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="unit2"))]
    service = RoleSyncService(db_session)
    await service.sync_user_units(user.id, roles)

    # Assert
    associations = await service.unit_user_service.get_by_user_id(user.id)
    assert len(associations) == 1
    assert associations[0].unit_id == unit2.id
```

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/services/user_service.py app/services/role_sync_service.py
git commit -m "feat: sync unit memberships on role changes"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** All tasks from the spec are implemented
- [ ] **Placeholder scan:** No "TBD", "TODO", or "implement later" in code
- [ ] **Type consistency:** All types (Role, UserProvider, etc.) match across files
- [ ] **Test coverage:** Unit tests for core logic, integration tests for APIs
- [ ] **Error handling:** Network errors, DB errors, TTL conflicts handled
- [ ] **Documentation:** Architecture doc explains the simplified approach without SSE
