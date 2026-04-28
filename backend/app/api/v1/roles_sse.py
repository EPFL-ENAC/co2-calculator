"""Server-Sent Events endpoint for role updates."""

import asyncio
import json
import logging
from datetime import datetime
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

        logger.info(
            "SSE connection established",
            extra={
                "user_id": current_user.id,
                "total_connections": len(active_connections),
            },
        )

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
                        yield 'data: {"type":"ping"}\n\n'
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
                extra={
                    "user_id": current_user.id,
                    "total_connections": len(active_connections),
                },
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
