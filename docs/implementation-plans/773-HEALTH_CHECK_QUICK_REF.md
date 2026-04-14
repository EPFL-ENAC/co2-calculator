# Health Check Endpoints - Quick Reference

## Endpoint Summary

| Endpoint   | Purpose              | Returns | Logging         | Used By                     |
| ---------- | -------------------- | ------- | --------------- | --------------------------- |
| `/healthz` | Liveness check       | 200 OK  | Never           | Kubernetes livenessProbe    |
| `/ready`   | Readiness check      | 200/503 | Only on failure | Kubernetes readinessProbe   |
| `/`        | Root (frontend only) | 200 OK  | Standard access | Frontend Docker HEALTHCHECK |

## Configuration Updates

### Backend (`backend/Dockerfile`)

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:${PORT}/ready || exit 1
```

### Frontend (`frontend/Dockerfile`)

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/ || exit 1
```

### Docker Compose (`docker-compose.yml`)

```yaml
healthcheck:
  test: ["CMD", "wget", "-qO-", "http://127.0.0.1:8000/ready"]
  interval: 10s
  timeout: 3s
  retries: 3
  start_period: 20s
```

### Kubernetes (`helm/values.yaml`)

```yaml
# Liveness Probe
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  periodSeconds: 20
  timeoutSeconds: 5
  failureThreshold: 5

# Readiness Probe
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3

# Startup Probe
startupProbe:
  httpGet:
    path: /healthz
    port: 8000
  periodSeconds: 2
  failureThreshold: 30
```

## Testing

### Manual Testing

```bash
# Test liveness endpoint
curl http://localhost:8000/healthz

# Test readiness endpoint
curl http://localhost:8000/ready

# Test frontend
curl http://localhost:3000/
```

### Automated Tests

```bash
cd backend
uv run pytest tests/integration/test_main.py -v
```

Expected output:

- ✅ test_root_endpoint
- ✅ test_healthz
- ✅ test_ready_db_ok
- ✅ test_ready_db_error
- ✅ test_ready_role_provider_skipped
- ✅ test_ready_role_provider_ok
- ✅ test_ready_role_provider_error
- ✅ test_main_block

## Migration Notes

### What Changed

- Old `/health` endpoint split into `/healthz` (liveness) and `/ready` (readiness)
- Success logging removed from health checks to reduce noise
- Docker and Compose configs updated to use `/ready`
- Frontend uses root `/` for health checks (no dedicated endpoint)

### What Stayed the Same

- Health check logic remains unchanged
- External provider checks still optional
- Database validation still performed
- Failure logging preserved for debugging

### Rollback Plan

If issues occur, revert to:

```yaml
# Kubernetes
livenessProbe:
  httpGet:
    path: /health  # Old endpoint
readinessProbe:
  httpGet:
    path: /health  # Old endpoint

# Docker
HEALTHCHECK CMD wget -qO- http://127.0.0.1:8000/health
```

Then update `backend/app/main.py` to rename `/ready` back to `/health`.

## Monitoring

### Key Metrics to Watch

- Pod restart frequency (should decrease)
- Log volume from health checks (should drop >80%)
- Readiness probe failure rate (should remain low)
- Application startup time (may improve with startup probe)

### Alerting

Keep existing alerts on:

- 503 responses from `/ready`
- Pod restarts
- Database connectivity issues

No alerts needed for:

- Successful `/healthz` calls (no logging)
- Successful `/ready` calls (no logging)
