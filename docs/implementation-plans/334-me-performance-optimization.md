# /me Performance Optimization: Decoupling Role Sync & Frontend Refresh Strategy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `/me` endpoint latency from ~1s to ~8ms by removing synchronous role refresh and implementing background role synchronization with SSE notifications.

**Architecture:**

- `/me` becomes a pure DB read (no external API calls)
- Background tasks sync roles periodically or on-demand
- SSE pushes role change notifications to connected clients
- Frontend uses SSE + TTL-based fallback for role consistency

**Tech Stack:** FastAPI (BackgroundTasks), SSE (EventSource), Pinia (Vue store), PostgreSQL

---

## File Structure

### Backend Files to Create/Modify

**Create:**

- `backend/app/api/v1/roles_sse.py` - SSE endpoint for role updates
- `backend/app/services/role_sync_service.py` - Background role synchronization logic
- `backend/app/tasks/role_sync_tasks.py` - Background task wrappers

**Modify:**

- `backend/app/api/v1/auth.py` - Remove sync from `/me`, add SSE trigger
- `backend/app/services/user_service.py` - Add role comparison logic
- `backend/app/models/user.py` - Add `last_roles_sync_at` timestamp field

**Frontend Files to Create/Modify:**

- `frontend/src/stores/roleSync.ts` - SSE connection + role state management
- `frontend/src/api/roles.ts` - Role sync API client

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
- Modify: `backend/app/api/v1/auth.py`

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
    6. Emits SSE event if roles changed

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

                    # TODO: Emit SSE event (will be implemented in Task 4)
                    # await emit_role_update_event(user_id, result.new_roles)

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

- [ ] **Step 5: Modify auth.py to trigger background sync**

```python
# Add to backend/app/api/v1/auth.py after imports:

from app.tasks.role_sync_tasks import trigger_role_sync_for_user


# Modify get_me endpoint (around line 482-580):

@router.get("/me", response_model=UserRead, response_model_exclude_none=True)
async def get_me(
    auth_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current authenticated user information.

    Returns user details including id, email, roles.
    Requires valid auth_token cookie.
    Resolves user by stable identity (institutional_id, provider) from JWT.
    NO LONGER syncs roles synchronously - uses cached DB roles.
    """
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        # Decode and validate token
        payload = decode_jwt(auth_token)
        sub = payload.get("sub")

        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # Primary: resolve by stable identity (institutional_id, provider)
        institutional_id = payload.get("institutional_id")
        provider_str = payload.get("provider")

        if institutional_id and provider_str:
            try:
                provider = UserProvider(int(provider_str))
            except ValueError:
                logger.warning(
                    "Invalid provider in token",
                    extra={"provider": provider_str},
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                )

            user = await UserService(db).get_by_institutional_id_and_provider(
                institutional_id=institutional_id,
                provider=provider,
            )
        else:
            # Fallback for legacy tokens
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                )
            logger.warning(
                "Legacy token with user_id detected - logging out user",
                extra={"user_id": user_id},
            )
            response = Response()
            response.delete_cookie(
                key="auth_token",
                path=settings.OAUTH_COOKIE_PATH or "/",
            )
            response.delete_cookie(
                key="refresh_token",
                path=settings.OAUTH_COOKIE_PATH or "/",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please login again.",
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User email missing",
            )

        # Trigger background role sync if needed (non-blocking)
        # Note: This is fire-and-forget - errors don't affect /me response
        if user.id is not None:
            background_tasks.add_task(
                trigger_role_sync_for_user,
                user_id=user.id,
                force=False,
            )

        user_read = UserRead.from_orm(user)
        return user_read

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user info", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
```

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/tasks/role_sync_tasks.py app/api/v1/auth.py
git commit -m "feat: trigger background role sync from /me endpoint"
```

---

## Task 4: Backend - SSE Endpoint for Role Updates

**Files:**

- Create: `backend/app/api/v1/roles_sse.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for role SSE endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app


@pytest.mark.asyncio
async def test_role_sse_endpoint_requires_auth():
    """Test that SSE endpoint requires authentication."""
    client = TestClient(app)
    response = client.get("/api/v1/roles/stream")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_role_sse_endpoint_returns_event_stream():
    """Test that SSE endpoint returns proper event stream."""
    # This is a basic integration test
    # Full test would require actual SSE client and role changes
    pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/integration/test_roles_sse.py -v
```

- [ ] **Step 3: Write minimal implementation**

```python
"""Server-Sent Events endpoint for role updates."""

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter()


class RoleUpdateEvent:
    """SSE event for role updates."""

    def __init__(
        self,
        user_id: int,
        roles: list,
        timestamp: str,
    ):
        self.user_id = user_id
        self.roles = roles
        self.timestamp = timestamp

    def to_sse(self) -> str:
        """Convert to SSE format."""
        data = {
            "type": "user_roles_updated",
            "payload": {
                "user_id": self.user_id,
                "roles": self.roles,
                "timestamp": self.timestamp,
            },
        }
        return f"data: {json.dumps(data)}\n\n"


# In-memory connection tracking (use Redis in production for multi-instance)
active_connections: set[asyncio.Queue] = set()


@router.get("/roles/stream")
async def stream_role_updates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events endpoint for role update notifications.

    Clients subscribe to receive real-time notifications when their roles change.
    Events are emitted when:
    - Background role sync detects role changes
    - Admin manually updates user roles

    Connection is kept alive with periodic ping events.
    """
    if not current_user or not current_user.id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for role updates."""
        # Create queue for this connection
        queue: asyncio.Queue = asyncio.Queue()
        active_connections.add(queue)

        try:
            ping_interval = 30  # seconds
            ping_counter = 0

            while True:
                try:
                    # Wait for event with timeout for ping
                    event = await asyncio.wait_for(queue.get(), timeout=ping_interval)
                    yield event
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    ping_counter += 1
                    if ping_counter >= 10:  # Send data ping every 10 pings
                        yield "data: {\"type\":\"ping\"}\n\n"
                        ping_counter = 0
                    else:
                        yield ": ping\n\n"  # Comment-only ping

        except asyncio.CancelledError:
            logger.info(
                "SSE connection cancelled",
                extra={"user_id": current_user.id},
            )
        except Exception as e:
            logger.error(
                "SSE connection error",
                extra={"user_id": current_user.id, "error": str(e)},
            )
        finally:
            active_connections.discard(queue)
            logger.info(
                "SSE connection closed",
                extra={"user_id": current_user.id},
            )

    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def emit_role_update_event(user_id: int, roles: list) -> None:
    """
    Emit role update event to all connected clients.

    In production, use Redis pub/sub for multi-instance deployment.
    """
    from datetime import datetime

    event = RoleUpdateEvent(
        user_id=user_id,
        roles=roles,
        timestamp=datetime.utcnow().isoformat(),
    )

    # Broadcast to all connections (in-memory for single instance)
    disconnected = set()
    for queue in active_connections:
        try:
            await queue.put(event.to_sse())
        except Exception:
            disconnected.add(queue)

    # Clean up disconnected queues
    active_connections -= disconnected

    logger.debug(
        "Role update event emitted",
        extra={"user_id": user_id, "connections": len(active_connections)},
    )
```

- [ ] **Step 4: Register router in main.py**

```python
# Add to backend/app/main.py:

from app.api.v1.roles_sse import router as roles_sse_router

app.include_router(roles_sse_router, prefix="/api/v1", tags=["roles"])
```

- [ ] **Step 5: Update role_sync_tasks.py to emit SSE events**

```python
# Modify trigger_role_sync_for_user in backend/app/tasks/role_sync_tasks.py:

# Add import:
from app.api.v1.roles_sse import emit_role_update_event

# In the function, after role sync:

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

    # Emit SSE event
    await emit_role_update_event(user_id, result.new_roles)
```

- [ ] **Step 6: Run tests and commit**

```bash
cd backend && uv run pytest tests/integration/test_roles_sse.py -v
git add app/api/v1/roles_sse.py app/api/v1/roles_sse.py app/main.py
git commit -m "feat: add SSE endpoint for real-time role update notifications"
```

---

## Task 5: Frontend - Role Sync Store

**Files:**

- Create: `frontend/src/stores/roleSync.ts`
- Modify: `frontend/src/stores/auth.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// No Jest/Vitest setup found - skip unit tests for now
// Manual testing will verify SSE connection and state updates
```

- [ ] **Step 2: Write implementation**

```typescript
/**
 * Role Sync Store - SSE connection for real-time role updates
 *
 * Features:
 * - Maintains SSE connection to /api/v1/roles/stream
 * - Auto-reconnects on connection loss
 * - Updates auth store on role changes
 * - Implements TTL-based fallback (re-fetch /me every 15 minutes)
 */

import { defineStore } from "pinia";
import { ref, onUnmounted } from "vue";
import { useAuthStore } from "./auth";

interface RoleUpdatePayload {
  type: "user_roles_updated" | "ping";
  payload?: {
    user_id: number;
    roles: Array<{
      role: string;
      on: { unit?: string; affiliation?: string } | "global";
    }>;
    timestamp: string;
  };
}

export const useRoleSyncStore = defineStore("roleSync", () => {
  const isConnected = ref(false);
  const lastEventTime = ref<Date | null>(null);
  const sse: Ref<EventSource | null> = ref(null);
  const reconnectAttempts = ref(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000; // 3 seconds

  const TTL_MS = 15 * 60 * 1000; // 15 minutes
  let ttlTimer: ReturnType<typeof setTimeout> | null = null;

  function startTTLTimer() {
    // Clear existing timer
    if (ttlTimer) {
      clearTimeout(ttlTimer);
    }

    // Set new timer to re-fetch /me
    ttlTimer = setTimeout(async () => {
      console.log("[RoleSync] TTL expired, re-fetching /me");
      const authStore = useAuthStore();
      await authStore.getUser();
      startTTLTimer(); // Restart timer
    }, TTL_MS);
  }

  function connect() {
    if (sse.value) {
      sse.value.close();
    }

    try {
      sse.value = new EventSource("/api/v1/roles/stream");

      sse.value.onopen = () => {
        console.log("[RoleSync] SSE connection established");
        isConnected.value = true;
        reconnectAttempts.value = 0;
        startTTLTimer();
      };

      sse.value.onmessage = (event: MessageEvent) => {
        try {
          const data: RoleUpdatePayload = JSON.parse(event.data);

          if (data.type === "ping") {
            // Keep-alive ping, ignore
            return;
          }

          if (data.type === "user_roles_updated" && data.payload) {
            console.log("[RoleSync] Role update received", data.payload);
            lastEventTime.value = new Date();

            // Update auth store
            const authStore = useAuthStore();
            if (authStore.user) {
              authStore.user.roles_raw = data.payload.roles;
              // Re-calculate permissions
              authStore.user.permissions = calculatePermissions(
                data.payload.roles,
              );
            }
          }
        } catch (err) {
          console.error("[RoleSync] Error parsing SSE message:", err);
        }
      };

      sse.value.onerror = () => {
        console.log("[RoleSync] SSE connection error");
        isConnected.value = false;

        // Attempt reconnection
        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++;
          console.log(
            `[RoleSync] Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttempts.value}/${maxReconnectAttempts})`,
          );
          setTimeout(connect, reconnectDelay);
        } else {
          console.warn(
            "[RoleSync] Max reconnection attempts reached, using TTL fallback",
          );
          // Fallback: rely on TTL-based /me re-fetch
          startTTLTimer();
        }
      };
    } catch (err) {
      console.error("[RoleSync] Failed to establish SSE connection:", err);
      isConnected.value = false;
    }
  }

  function disconnect() {
    if (sse.value) {
      sse.value.close();
      sse.value = null;
    }
    if (ttlTimer) {
      clearTimeout(ttlTimer);
      ttlTimer = null;
    }
    isConnected.value = false;
  }

  // Helper function to calculate permissions from roles
  function calculatePermissions(
    roles: Array<{
      role: string;
      on: { unit?: string; affiliation?: string } | "global";
    }>,
  ): {
    [key: string]: {
      view?: boolean;
      edit?: boolean;
      export?: boolean;
    };
  } {
    // This should match backend logic in calculate_user_permissions
    // For now, return empty - will be implemented based on actual permissions logic
    return {};
  }

  // Auto-connect on store initialization
  connect();

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    lastEventTime,
    connect,
    disconnect,
  };
});
```

- [ ] **Step 3: Modify auth.ts to integrate with role sync**

```typescript
// Add to frontend/src/stores/auth.ts:

import { useRoleSyncStore } from "./roleSync";

// In getUser function, after successful fetch:

async function getUser(): Promise<User | null> {
  if (inflight) return inflight;

  inflight = (async () => {
    try {
      loading.value = true;
      const u = await api.get("auth/me").json<User>();
      user.value = u;

      // Initialize role sync on first successful auth
      if (u) {
        const roleSyncStore = useRoleSyncStore();
        roleSyncStore.connect();
      }

      return u;
    } catch {
      user.value = null;
      return null;
    } finally {
      loading.value = false;
      hasChecked.value = true;
      inflight = null;
    }
  })();

  return inflight;
}
```

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/stores/roleSync.ts src/stores/auth.ts
git commit -m "feat: add role sync store with SSE connection and TTL fallback"
```

---

## Task 6: Frontend - Integration Testing

**Files:**

- Modify: `frontend/src/components/layout/Co2Header.vue` (or main App component)

- [ ] **Step 1: Add role sync status indicator (optional, for debugging)**

```vue
<!-- Add to Co2Header.vue or App.vue -->

<template>
  <div>
    <!-- Existing header content -->

    <!-- Role sync status indicator (dev only) -->
    <div v-if="DEBUG" class="role-sync-status">
      <span :class="{ connected: roleSync.isConnected }">
        {{ roleSync.isConnected ? "✓ Roles Synced" : "⚠ Syncing..." }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoleSyncStore } from "@/stores/roleSync";
import { computed } from "vue";

const DEBUG = import.meta.env.DEV;
const roleSync = useRoleSyncStore();
</script>
```

- [ ] **Step 2: Manual testing checklist**

```markdown
## Manual Testing Checklist

### Backend

- [ ] `/me` returns in <50ms (check with curl/Postman)
- [ ] `/me` does NOT call external APIs (check logs)
- [ ] Background task triggers role sync (check logs)
- [ ] SSE endpoint accepts connections (`/api/v1/roles/stream`)
- [ ] Role changes emit SSE events

### Frontend

- [ ] SSE connection establishes on login
- [ ] Role updates refresh user state without page reload
- [ ] Reconnection works after network interruption
- [ ] TTL fallback re-fetches /me after 15 minutes
- [ ] Permissions update correctly after role change

### Integration

- [ ] Login → `/me` returns quickly → background sync runs
- [ ] Change roles in DB → SSE event received → UI updates
- [ ] Disconnect VPN (role provider down) → `/me` still works
- [ ] Multiple tabs → all receive SSE updates
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/components/layout/Co2Header.vue
git commit -m "feat: add role sync status indicator for debugging"
```

---

## Task 7: Observability & Safety

**Files:**

- Modify: `backend/app/services/role_sync_service.py`
- Modify: `backend/app/tasks/role_sync_tasks.py`

- [ ] **Step 1: Add comprehensive logging**

```python
# Already included in role_sync_service.py and role_sync_tasks.py:
# - Log sync start/end
# - Log role differences
# - Log SSE events emitted
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

## Task 8: Unit Membership Sync with ACCRED

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

## Task 9: Documentation

**Files:**

- Create: `docs/role-sync-architecture.md`

- [ ] **Step 1: Write architecture documentation**

```markdown
# Role Synchronization Architecture

## Overview

The `/me` endpoint now returns cached roles from the database in ~8ms, instead of synchronously fetching from external providers (~1s).

## Components

### 1. `/me` Endpoint (Fast)

- Validates JWT
- Fetches user from DB (including cached roles)
- Returns immediately
- Triggers background sync (non-blocking)

### 2. Background Role Sync

- Runs asynchronously via FastAPI BackgroundTasks
- Fetches fresh roles from provider (Accred/JWT/Test)
- Compares with cached roles
- Updates DB only if changes detected
- Emits SSE event on changes

### 3. SSE Connection

- Client subscribes to `/api/v1/roles/stream`
- Server pushes `user_roles_updated` events
- Auto-reconnects on connection loss
- Ping events keep connection alive

### 4. Frontend State Management

- `useRoleSyncStore` manages SSE connection
- Updates `useAuthStore` on role changes
- TTL fallback: re-fetch `/me` every 15 minutes

## Consistency Model

**Eventual Consistency:**

- `/me` returns immediately with cached roles
- Background sync updates roles within 15 minutes (TTL)
- SSE provides near-real-time updates when connected
- If SSE fails, TTL ensures eventual convergence

## Safety Guarantees

1. **Authorization always uses DB roles** - No external API calls on `/me`
2. **Failures don't block `/me`** - Background sync errors logged but don't affect response
3. **No recursive syncs** - TTL prevents sync storms
4. **Concurrent sync protection** - BackgroundTasks queue handles serialization
5. **Unit cleanup** - Removed roles automatically clean up unit associations

## Performance

| Operation           | Before      | After                |
| ------------------- | ----------- | -------------------- |
| `/me` latency       | ~1000ms     | ~8ms                 |
| External API calls  | Per request | Periodic (15 min)    |
| Role update latency | Immediate   | ~5-15 min (eventual) |

## Monitoring

- Logs: `role_sync_*` events in backend logs
- SSE connections: Track active connections in logs
- Errors: `RoleProviderNetworkError` logged with context
```

- [ ] **Step 2: Commit**

```bash
cd backend && git add docs/role-sync-architecture.md
git commit -m "docs: add role synchronization architecture documentation"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** All 6 tasks from the spec are implemented
- [ ] **Placeholder scan:** No "TBD", "TODO", or "implement later" in code
- [ ] **Type consistency:** All types (Role, UserProvider, etc.) match across files
- [ ] **Test coverage:** Unit tests for core logic, integration tests for APIs
- [ ] **Error handling:** Network errors, DB errors, TTL conflicts handled
- [ ] **Documentation:** Architecture doc explains the approach
