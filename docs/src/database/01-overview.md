# Database Overview

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
- See [erd.md](erd.md) and [draft-erd.dbml](draft-erd.dbml) for schema diagrams.

## ORM Integration

- Models use SQLAlchemy 2.0 (`backend/app/models/`).
- Do **not** use PostgreSQL-specific SQLAlchemy dialects (e.g., `func.array_agg()`), so tests run on SQLite in-memory.
- Example test run:
  ```bash
  pytest  # Uses SQLite automatically
  ```

## Notes

- Connection pooling (e.g., pgbouncer) is not yet implemented, but the app is compatible via `DB_URL`.
- For table/index details, see [erd.md](erd.md) and [draft-erd.dbml](draft-erd.dbml).

---

**Last Updated**: November 20, 2025
