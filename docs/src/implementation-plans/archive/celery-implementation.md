---
status: abandoned
last_updated: 2026-01-20
title: "Step 0 — Prep"
summary: "This gives you a clear separation of responsibilities."
---

> **ARCHIVED:** This plan was not delivered. Preserved for context.

## **Step 0 — Prep**

- Pick a **Celery broker** (Redis or RabbitMQ)
- Decide on **task/result handling** (Postgres remains source of truth)
- Ensure your **services/data_ingestion** is **pure business logic**, no Celery or BackgroundTasks

---

## **Step 1 — Add Celery bootstrap**

1. Create `celery_app.py`:

```python
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.autodiscover_tasks(["app.tasks"])
```

2. Keep **FastAPI imports separate** to avoid side effects

---

## **Step 2 — Move worker orchestration to `tasks/`**

1. Create `tasks/ingestion_tasks.py`
2. Wrap your current worker function in a Celery task
3. Use **serializable arguments only** (IDs, strings, dicts)
4. Inside the task:
   - reconstruct provider/service
   - update job status in Postgres (`RUNNING`, `SUCCESS`, `FAILED`)

```python
@celery_app.task(bind=True)
def run_ingestion(provider_name: str, job_id: int, filters: dict):
    # Reconstruct provider & service
    # Update job status
    # Run logic
```

---

## **Step 3 — Refactor FastAPI route**

- Remove `background_tasks.add_task(...)`
- Enqueue Celery task instead:

```python
job_id = await provider.create_job(...)
run_ingestion.delay(
    provider_name=provider.__class__.__name__,
    job_id=job_id,
    filters=request.filters,
)
```

- The API is now **thin, only I/O + enqueue**

---

## **Step 4 — Separate responsibilities**

| Layer          | Responsibility                    |
| -------------- | --------------------------------- |
| `api`          | HTTP, auth, enqueue, SSE          |
| `tasks`        | Orchestration, retries, lifecycle |
| `services`     | Pure business logic, reusable     |
| `repositories` | DB access                         |
| `models`       | ORM/SQLModel                      |
| `db`           | DB connection + migrations        |

---

## **Step 5 — SSE / frontend updates**

1. Use **Postgres as authoritative source**
2. Two options:
   - **Option A:** LISTEN / NOTIFY
     - Celery task calls `NOTIFY job_updates, ...`
     - FastAPI SSE endpoint streams notifications

   - **Option B:** Poll DB in SSE loop (simpler but more load)

```python
@app.get("/jobs/stream")
async def job_stream():
    async for payload in listen_pg("job_updates"):
        yield {"event": "job_update", "data": payload}
```

---

## **Step 6 — Docker / Deployment**

- **One Docker image** for both API and worker
- Override CMD/entrypoint:

```yaml
# docker-compose example
api:
  image: backend:latest
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000

worker:
  image: backend:latest
  command: celery -A app.celery_app worker -l info
```

---

## **Step 7 — Optional improvements**

- Add **idempotency** in tasks (use job_id)
- Add **retry policy** via Celery
- Add **queues** if different ingestion types require prioritization

---

### ✅ Outcome

- FastAPI is **fast and decoupled**
- Celery handles **all background tasks**
- Job status remains in Postgres
- Frontend can receive **near-real-time updates via SSE**
- Clear separation of concerns prevents coupling or code drift

---

### **visual mini-diagram + “before vs after” table”** so you have a one-page reference for

---

## **Before: FastAPI BackgroundTasks**

```
Client
  │
  ▼
FastAPI API ──> background_tasks.add_task(run_sync_task)
  │
  └─ executes job in same process/thread
       │
       └─ services/data_ingestion/*.py
            │
            └─ repositories → Postgres
```

**Drawbacks:**

- API thread blocked until DB writes complete
- No retries / limited lifecycle
- Hard to scale horizontally

---

## **After: Celery + SSE**

```
Client
  │
  ▼
FastAPI API ──> enqueue task ──> Broker (Redis/RabbitMQ)
  │                                  │
  │                                  ▼
  │                          Celery Worker(s)
  │                                  │
  │                          call services/data_ingestion
  │                                  │
  │                          repositories → Postgres
  │                                  │
  │                  NOTIFY / update job status
  ▼
Frontend SSE endpoint ──────────────┘
(listens for Postgres notifications)
```

**Benefits:**

- API never blocks, only enqueues
- Workers handle retries, concurrency, scaling
- Job status in Postgres = source of truth
- Frontend updates in near-real-time via SSE

---

💡 **Mental model:**

```
API = I/O & enqueue
Tasks = orchestration
Services = business logic
Repositories = DB access
DB = state + event source
```

This gives you a **clear separation of responsibilities**.

```ascii
#
#        ┌───────────────┐
#        │   Frontend    │
#        │  (React / JS) │
#        └───────┬───────┘
#                │
#                ▼
#        ┌───────────────┐
#        │   FastAPI     │
#        │   API Router  │
#        └───────┬───────┘
#                │
#                │ create job in DB
#                │ enqueue Celery task
#                ▼
#        ┌───────────────┐
#        │   Redis       │  <-- Celery Broker
#        │   (Queue)     │
#        └───────┬───────┘
#                │
#                ▼
#        ┌───────────────┐
#        │  Celery Worker │
#        │ (Python app)  │
#        └───────┬───────┘
#                │
#                │ calls
#                ▼
#    ┌─────────────────────────┐
#    │ services/data_ingestion │
#    │  (process job based on  │
#    │   entity_type / meta)   │
#    └───────┬─────────────────┘
#            │
#            ▼
#        ┌───────────────┐
#        │   Postgres    │  <-- DataIngestionJob table + results
#        │  (job status) │
#        └───────┬───────┘
#                │
#        NOTIFY / LISTEN
#                │
#                ▼
#        ┌───────────────┐
#        │   Frontend    │
#        │  (SSE / Live) │
#        └───────────────┘
```
