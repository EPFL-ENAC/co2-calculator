# Database Overview

> 📘 **See also:** [Current ER diagram](./erd.md) — the canonical schema reference.

The application connects to PostgreSQL using the `DB_URL` environment variable, supporting any accessible PostgreSQL instance (local, remote, DSI-hosted, pgbouncer, Kubernetes, etc.). This ensures modularity and scalability—just update `DB_URL` as needed.

## Local Development

- Start a local PostgreSQL instance:
  ```bash
  docker-compose up -d postgres
  ```
- Create a `.env` file in `backend/` or copy .env.example and change accordingly:
  ```env
  DB_URL=postgresql://co2calculator:password@postgres:5432/co2calculator
  ```
- Start backend and frontend:

  ```bash
  # Terminal 1
  cd backend
  make dev

  # Terminal 2
  cd frontend
  npm run dev
  ```

## Running All Services with Docker Compose

- To run all services (backend, frontend, db):
  ```bash
  docker-compose up -d
  ```
- Ensure `.env` is configured as above for backend connectivity.
- Change the host in DB_URL to match the postgresql service name in the docker-compose file

## Remote/Production Environments

- Set `DB_URL` to your remote DB (DSI, cloud, etc.):
  ```env
  DB_URL=postgresql://user:password@db.example.com:5432/co2calculator?sslmode=require
  ```
- For Kubernetes/Helm, configure `values.yaml`:
  ```yaml
  database:
    existingSecret:
      name: "db-secret"
      keys:
      # use for backend and migrations job
      url: DB_URL
  ```
- Migrations run automatically via an job on deployment. To check migration jobs:
  ```bash
  kubectl logs -f job/migration
  ```

## Schema & Migrations

- All environments (local, remote) are aligned using Alembic migrations.
- To create and apply migrations:
  ```bash
  cd backend
  make db-revision message="Add column"
  make db-migrate
  ```
- Migrations are applied automatically in Helm deployments via a cron job via helm hook on post-install, post-upgrade
- See [erd.md](erd.md) for the schema diagram.

## ORM Integration

- Models use SQLAlchemy 2.0 (`backend/app/models/`).
- Do **not** use PostgreSQL-specific SQLAlchemy dialects (e.g., `func.array_agg()`), so tests run on SQLite in-memory.
- Example test run:
  ```bash
  pytest  # Uses SQLite automatically
  ```

## Notes

- **PgBouncer sits in front of every DBaaS instance** (dev, stage, prod —
  confirmed by DBaaS on 2026-09-08). The app still connects to port 5432 via
  `DB_URL`; SQLAlchemy's in-process pool (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`,
  set per environment in `openshift-app-config`) is the client side of it.
  Consequences:
  - The bouncer's server pool, not Postgres `max_connections`, is the
    connection ceiling. The `db.server.connections` gauge reads that pool
    (~35 in dev). The "1000" DBaaS quotes is most likely `max_client_conn`.
  - A client that waits past the bouncer's `query_wait_timeout` (~120 s)
    gets `psycopg.errors.ProtocolViolation: query_wait_timeout` — dev
    logged exactly that on 2026-09-08 while the SQLAlchemy pool was far
    from full.
  - `pool_mode` and `default_pool_size` are **not confirmed yet**. Under
    transaction pooling every open transaction pins a server slot: the
    request-scoped session from `get_db` holds one for the whole request
    (the general case of #2654), and a long ingest holds one for its whole
    run. Ask DBaaS (`SHOW POOLS`) before changing any pool number.
    Since #2689 `get_current_user` hands its connection back before the
    route body runs, so a request holds a connection only from its own
    first query to the end of the response.
  - The `db.server.connections` gauge is emitted by the pod heartbeat,
    which blocks at the bouncer during a stall, so a flat line _during_ an
    incident is a frozen value. The ~40 plateau seen on four separate days
    in dev is the effective ceiling.
- For table/index details, see [erd.md](erd.md).

---

**Last Updated**: November 20, 2025
