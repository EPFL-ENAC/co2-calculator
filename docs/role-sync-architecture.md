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

## Implementation Details

### Database Schema

Added `last_roles_sync_at` timestamp field to User model to track when roles were last synced from provider.

### Role Sync Service

`RoleSyncService` handles:

- TTL-based sync throttling (15 minutes default)
- Role comparison (old vs new)
- User role updates
- Unit membership synchronization

### Background Tasks

`trigger_role_sync_for_user` function:

- Fetches user from DB
- Gets role provider based on user provider type
- Fetches fresh roles from external provider
- Calls `RoleSyncService.sync_user_roles()`
- Emits SSE event if roles changed

### SSE Endpoint

`/api/v1/roles/stream`:

- Requires authentication
- Maintains connection with ping events (30s interval)
- Broadcasts role update events to all connected clients
- In-memory connection tracking (Redis pub/sub for production multi-instance)

### Frontend Integration

`useRoleSyncStore`:

- Auto-connects on auth store initialization
- Listens for `user_roles_updated` events
- Updates auth store roles_raw on event
- Reconnects with exponential backoff on error
- TTL fallback: re-fetch `/me` every 15 minutes

## Future Enhancements

1. **Redis pub/sub** for multi-instance deployments
2. **Metrics** for sync latency and role change frequency
3. **Admin API** to manually trigger role sync
4. **Role change audit logging** for compliance
5. **WebSocket support** for bidirectional communication
