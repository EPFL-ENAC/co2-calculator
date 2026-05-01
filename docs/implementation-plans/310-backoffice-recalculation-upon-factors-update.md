Got it — you’re not building a fixed 3-step pipeline, you’re building a **generic DAG runner over multiple workflows**. That’s an important correction.

So instead of hardcoding `INGEST/EMISSIONS/AGGREGATE`, your system should treat steps as **data-driven tasks**, not enum-driven stages.

---

# 🧠 Compact mental model (everything we discussed)

## What you are building

A **Postgres-backed workflow engine**:

- Jobs = execution units
- State = lifecycle (`PENDING → RUNNING → DONE/FAILED`)
- Payload = everything needed to run a step
- Steps = dynamic (not enum)
- DAG = created by enqueueing next jobs

---

## Core architecture

### 3-layer pipeline:

### 1. Ingestion (raw input)

- CSV/API/manual
- writes `data_entries`
- no business logic

---

### 2. Computation (fan-out layer)

- builds `data_entry_emissions`
- heavy parallelism
- idempotent transformations

---

### 3. Aggregation (single writer layer)

- builds `carbon_reports`
- ONLY writer of aggregates
- always `ON CONFLICT DO UPDATE`

---

## Key rule that fixes your concurrency bugs

> Only ONE job type writes a given table.

---

## Concurrency model

- Postgres `SKIP LOCKED` = queue
- batching = load control
- `ON CONFLICT` = idempotency
- DAG = job chaining (not status logic)

---

## Why your enum idea breaks

You’re right:

- `INGEST / EMISSIONS / AGGREGATE` ❌ too rigid
- different flows (csv, factors, recompute, etc.)

So instead:

👉 steps must be **payload-defined job handlers**, not enums

---

# ✅ TODO LIST (clean + actionable)

## 🧱 1. Fix job model (foundation)

- [ ] Keep existing `DataIngestionJob` table
- [ ] **DO NOT add hardcoded JobStep enum**
- [ ] Introduce `job_type: TEXT` instead (e.g. `"csv_ingest"`, `"factor_recompute"`)
- [ ] Ensure `payload: JSONB` fully defines behavior
- [ ] Add optional `pipeline_id (UUID)` to group runs
- [ ] Keep `state` + `result` as execution tracking only

---

## ⚙️ 2. Implement proper job queue mechanics

- [ ] Implement worker job claiming using:
  - `SELECT ... FOR UPDATE SKIP LOCKED`

- [ ] Add `run_after` for scheduling retries
- [ ] Add `attempts / max_attempts`
- [ ] Add `locked_by` for debugging
- [ ] Ensure idempotent job execution (critical)

---

## 📦 3. Fix batching strategy (VERY important for your case)

- [ ] CSV ingestion batch size: **1k–5k rows**
- [ ] emissions computation batch size: **50–200 entries**
- [ ] DB insert batch size: **1k–10k rows (emissions)**
- [ ] Ensure NO single transaction processes full CSV

---

## 🧠 4. Split pipeline responsibilities (core refactor)

- [ ] Ingestion job:
  - only writes `data_entries`
  - NEVER writes emissions or aggregates

- [ ] Emissions job:
  - reads `data_entries`
  - writes `data_entry_emissions`
  - enqueues aggregation job

- [ ] Aggregation job:
  - reads emissions
  - writes `carbon_reports`
  - uses `ON CONFLICT DO UPDATE`

---

## 🔁 5. Replace “step enum” with dynamic workflow logic

- [ ] Replace fixed step model with:
  - `job_type`
  - `payload["handler"]`

- [ ] Implement handler registry in Python:

```python
handlers = {
  "csv_ingest": handle_ingest,
  "compute_emissions": handle_emissions,
  "compute_aggregates": handle_aggregates,
}
```

- [ ] Ensure each handler is independent & idempotent

---

## 🚦 6. Fix concurrency bugs (your original problem)

- [ ] Add `ON CONFLICT` everywhere needed:
  - data_entries
  - emissions
  - carbon_reports

- [ ] Ensure only ONE job type writes `carbon_reports`
- [ ] Remove any parallel writes to same aggregate table

---

## 📊 7. Add observability (minimum viable)

- [ ] Log job transitions (`PENDING → RUNNING → DONE`)
- [ ] Store error messages in `status_message`
- [ ] Track job duration
- [ ] Track retry counts
- [ ] Add simple dashboard query:

```sql
SELECT state, count(*) FROM jobs GROUP BY state;
```

---

## 🔄 8. Introduce DAG chaining (simple version)

- [ ] After job completion, enqueue next job explicitly
- [ ] Encode dependencies in payload:

```json
{
  "next_job": "compute_emissions",
  "dataset_id": 123
}
```

- [ ] Avoid complex dependency tables for now

---

## 🧪 9. Load safety controls

- [ ] Add per-worker semaphore (soft concurrency limit)
- [ ] Limit concurrent DB connections per pod
- [ ] Monitor DB lock time & slow queries
- [ ] Cap worker concurrency (start low: 2–5)

---

## 🚀 10. Optional (only if needed later)

- [ ] Add Postgres `job_dependencies` table (only if DAG grows complex)
- [ ] Add retry backoff system
- [ ] Add job priority queues
- [ ] Consider Celery ONLY if:
  - scheduling becomes complex
  - retries + workflows explode in complexity

---

# 🧭 Final mental model

What you end up with:

> Postgres is your queue
> Python is your orchestrator
> JSON is your workflow definition
> Tables are your state

---

### 🧠 Compact summary of the whole discussion

You’re building a **multi-stage data pipeline (DAG)** in FastAPI + Postgres:

---

## ⚠️ Core problem you hit

- You were running ingestion + emissions + aggregation in the same flow
- Multiple workers wrote to `carbon_reports` concurrently
- Even with idempotency, you got:
  - race conditions
  - duplicate key violations
  - inconsistent derived state

---

## 🧩 Root cause

You mixed:

- raw data ingestion
- derived computations
- final aggregation

👉 All in one execution path → **concurrency conflicts**

---

## 🏗️ Correct architecture (what we converged to)

### 3 independent pipeline stages:

1. **Ingestion**
   - CSV/API → `data_entries`
   - batch inserts (≈ 1k–5k rows)
   - idempotent (`ON CONFLICT`)

2. **Emissions computation (fan-out)**
   - `data_entries → data_entry_emissions`
   - heavy parallelism allowed
   - smaller worker batches (≈ 50–200 entries)

3. **Aggregation**
   - `data_entry_emissions → carbon_reports`
   - ONLY writer of `carbon_reports`
   - `ON CONFLICT DO UPDATE`

---

## 🚫 Key design correction

- ❌ Do NOT compute emissions inside ingestion transaction
- ❌ Do NOT write aggregates from multiple jobs
- ❌ Do NOT use BackgroundTasks for orchestration

---

## ⚙️ Execution model (no Celery needed)

You use Postgres as a queue:

- `jobs` table
- `FOR UPDATE SKIP LOCKED` for concurrency safety
- job chaining via explicit enqueueing

---

## 🧠 Status system fix

Old:

- PENDING / VALIDATED / REJECTED → ❌ wrong abstraction

New:

- INGESTED → PROCESSED → FAILED (execution state)
- VALID/INVALID (optional separate validation dimension)

👉 status ≠ workflow control anymore, only observability

---

## 📦 Batching strategy

- CSV ingestion: 1k–5k rows per transaction
- emissions: 50–200 entries per batch
- emissions inserts: 1k–10k rows per bulk insert

---

## 🔥 Key concurrency fix

- Only ONE workflow writes `carbon_reports`
- All derived writes isolated per stage
- `ON CONFLICT` used everywhere needed

---

## ❗ Important insight

You are NOT building:

> a CSV importer

You are building:

> a **multi-stage ETL pipeline with fan-out + aggregation**

---

## 🧭 Final architecture shape

```
CSV/API
  ↓
data_entries (ingestion)
  ↓
data_entry_emissions (fan-out compute)
  ↓
carbon_reports (aggregation)
```

All orchestrated via:

- Postgres job queue
- SKIP LOCKED workers
- explicit job chaining

---

## 🚀 Decision outcome

- ❌ No Celery needed (for now)
- ❌ No fixed “step enum”
- ✅ Dynamic job types instead
- ✅ Postgres-native workflow engine
- ✅ DAG via job chaining
- ✅ deterministic concurrency model

---
