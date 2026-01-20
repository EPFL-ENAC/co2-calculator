Here is a **single, unified implementation plan**, consolidating everything into **one coherent spec-driven plan**, without repetitions or competing versions.

---

# 🎯 Unified Implementation Plan: Generic Data Ingestion & Sync System

## Goal

Build a **generic, extensible, provider-based data ingestion system** that can sync **data entries** and **emission factors** from multiple sources (CSV, Tableau API, future APIs), with:

- Consistent **job tracking**
- Background execution
- Clear **API contracts**
- Pluggable providers
- Frontend-friendly progress reporting

This plan follows **Spec-Driven Development**: contracts first (DB, API, class interfaces), implementation second.

---

## 1. Architecture Overview

### Core Principles

- **Providers encapsulate source-specific logic** (Tableau, CSV, etc.)
- **The pipeline is generic** (status tracking, error handling, background execution)
- **Adding a new provider = adding one class + registry entry**
- **Frontend never knows provider internals**, only job IDs and statuses

### Design Patterns

- **Template Method** → shared ingestion lifecycle
- **Strategy Pattern** → interchangeable providers
- **Factory Pattern** → safe provider instantiation
- **State Machine** → strict job state transitions

---

## 2. Database Contract (Source of Truth)

### `data_ingestion_jobs`

Tracks every sync attempt (data entries or factors).

```sql
CREATE TABLE data_ingestion_jobs (
    id SERIAL PRIMARY KEY,
    inventory_id INT NOT NULL REFERENCES inventories(id),
    module_id INT REFERENCES modules(id),
    factor_type_id INT REFERENCES factor_types(id),

    provider_type VARCHAR(50) NOT NULL,     -- csv_upload, tableau_api, etc.
    target_type VARCHAR(20) NOT NULL,       -- data_entries | factors
    year INT NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    status_code INT,
    message TEXT,

    metadata JSONB DEFAULT '{}',             -- progress, filters, config, errors
    created_by INT REFERENCES users(id),

    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_jobs_module ON data_ingestion_jobs(module_id);
CREATE INDEX idx_jobs_status ON data_ingestion_jobs(status);
```

### `modules` Optimization Field

```sql
ALTER TABLE modules ADD COLUMN last_sync_status JSONB DEFAULT '{}';
-- { provider, status, last_run, last_job_id }
```

This avoids heavy history queries for UI badges.

---

## 3. API Contract (Generic & Scalable)

### A. Sync Data Entries

**POST** `/api/v1/sync/data-entries/{module_id}`

```json
{
  "provider_type": "tableau_api",
  "year": 2025,
  "filters": { "centre_financier": "F0892" },
  "config": {}
}
```

**Response**

```json
{
  "job_id": 123,
  "status": "pending",
  "status_code": 102,
  "message": "Sync initiated"
}
```

---

### B. Sync Emission Factors

**POST** `/api/v1/sync/factors/{module_id}/{factor_type_id}`
Same payload structure, usually `csv_upload`.

---

### C. Poll Job Status

**GET** `/api/v1/sync/status/{job_id}`

```json
{
  "job_id": 123,
  "status": "processing",
  "status_code": 103,
  "message": "Fetched 245 rows",
  "progress": { "fetched": 245 }
}
```

---

### D. Sync History

**GET** `/api/v1/sync/history/{module_id}?provider_type=tableau_api&limit=20`

---

### E. Retry Failed Job

**POST** `/api/v1/sync/retry/{job_id}`

---

## 4. Provider System (Internal Contract)

### Abstract Base Provider (The Contract)

All providers must implement this lifecycle.

```python
class DataIngestionProvider(ABC):

    provider_name: str        # csv_upload, tableau_api
    target_type: str          # data_entries | factors

    async def validate_connection(self) -> bool
    async def fetch_data(self, filters: dict) -> list[dict]
    async def transform_data(self, raw: list[dict]) -> list[dict]
    async def load_data(self, clean: list[dict]) -> dict

    async def run_pipeline(self):
        """
        1. Job → processing
        2. validate_connection
        3. fetch_data
        4. transform_data
        5. load_data
        6. Job → completed
        7. On error → failed
        """
```

This guarantees **identical behavior across all providers**.

---

## 5. Provider Factory (Single Entry Point)

Prevents invalid combinations (e.g. Tableau + Headcount).

```python
REGISTRY = {
  ('travel', 'tableau_api', 'data_entries'): TableauFlightsProvider,
  ('travel', 'csv_upload', 'data_entries'): CSVTravelProvider,
  ('headcount', 'csv_upload', 'data_entries'): CSVHeadcountProvider,
  ('generic', 'csv_upload', 'factors'): CSVFactorsProvider,
}
```

Factory responsibilities:

- Resolve provider
- Instantiate with correct context
- Recreate provider from job metadata (retry)

---

## 6. Concrete Providers

### TableauFlightsProvider (Travel / Data Entries)

Responsibilities:

- Authenticate via JWT
- Query Tableau with `year` filter
- Normalize travel class
- Map Tableau fields → `carbon_reports` schema
- Bulk insert via existing CRUD

No job logic, no API logic — **only business logic**.

---

### CSV Providers

- `CSVDataEntriesProvider`
  → generic, module-aware CSV ingestion

- `CSVFactorsProvider`
  → emission factors only, tied to `factor_type_id`

---

## 7. Background Execution

- FastAPI `BackgroundTasks`
- Each job runs `provider.run_pipeline()`
- Progress updates stored in `metadata.progress`
- UI polls status endpoint

---

## 8. Frontend Integration

Single reusable UI flow:

1. User selects:
   - Provider
   - Year
   - Optional filters

2. POST `/sync/...`
3. Receive `job_id`
4. Poll `/sync/status/{job_id}`
5. Show progress / success / failure
6. Allow retry if failed

---

## 9. Implementation Phases

### Phase 1 — Foundation

- DB migration
- Job CRUD
- Base provider with lifecycle
- API endpoints (no providers yet)

### Phase 2 — Core Logic

- ProviderFactory
- Background task runner
- Status updates + metadata

### Phase 3 — Providers

- TableauFlightsProvider
- CSVDataEntriesProvider
- CSVFactorsProvider

### Phase 4 — Integration

- Frontend sync button
- Polling UI
- Retry flow
- Module status badges

---

## 10. Final Checklist

- [ ] `data_ingestion_jobs` table
- [ ] Generic sync API
- [ ] Base provider contract
- [ ] Provider factory + registry
- [ ] Tableau travel ingestion
- [ ] CSV ingestion (entries + factors)
- [ ] Background execution
- [ ] Status polling & retry
- [ ] UI integration

---

## ✅ Result

You end up with a **clean, scalable ingestion platform** where:

- New APIs are added without touching routes
- CSV, API, manual entry all behave the same
- Jobs are observable, retryable, auditable
- Frontend logic stays generic forever

If you want, I can now:

- Turn this into a **formal ADR**
- Produce a **sequence diagram**
- Extract a **minimal MVP version**
- Or generate **OpenAPI schemas** directly from this plan
