# Role Synchronization Architecture

## Overview

The `/refresh` endpoint triggers background role synchronization, while `/me` returns cached roles from the database in ~8ms without triggering sync.

## Components

### 1. `/me` Endpoint (Fast)

- Validates JWT
- Fetches user from DB (including cached roles)
- Returns immediately
- No background sync triggered

### 2. `/refresh` Endpoint (Triggers Sync)

- Validates JWT
- Fetches user from DB
- Triggers background role sync (non-blocking)
- Returns user info with cached roles

### 3. Background Role Sync

- Runs asynchronously via FastAPI BackgroundTasks
- Fetches fresh roles from provider (Accred/JWT/Test)
- Compares with cached roles
- Updates DB only if changes detected

## Consistency Model

**Eventual Consistency:**

- `/me` returns immediately with cached roles
- `/refresh` triggers background sync within 15 minutes (TTL)
- TTL ensures eventual convergence
- Manual sync trigger via `/refresh` when needed

## Safety Guarantees

1. **Authorization always uses DB roles** - No external API calls on `/me`
2. **Failures don't block endpoints** - Background sync errors logged but don't affect response
3. **No recursive syncs** - TTL prevents sync storms
4. **Concurrent sync protection** - BackgroundTasks queue handles serialization
5. **Unit cleanup** - Removed roles automatically clean up unit associations

## Performance

| Operation           | Before      | After                  |
| ------------------- | ----------- | ---------------------- |
| `/me` latency       | ~1000ms     | ~8ms                   |
| `/refresh` latency  | ~1000ms     | ~8ms + background sync |
| External API calls  | Per request | Periodic (15 min)      |
| Role update latency | Immediate   | ~5-15 min (eventual)   |

## Monitoring

- Logs: `role_sync_*` events in backend logs
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

### Frontend Integration

- TTL-based fallback: re-fetch `/me` periodically if needed
- Manual refresh via `/refresh` endpoint when user explicitly requests sync
