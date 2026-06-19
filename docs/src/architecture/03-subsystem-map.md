---
status: delivered
last_updated: 2026-06-16
summary: Internal subsystem map of the co2-calculator app — in-cluster units and the backend's components, drawn from the Helm chart, code and the live OpenShift namespace.
---

# Subsystem Map

The in-cluster view of **our app only**: the deployable units and the
backend's internal subsystems, reconciled against the Helm chart, the
backend code and the live OpenShift namespace. For the wider platform and
supply chain (GitHub, registry, ArgoCD, external services, observability)
see [System Overview](./02-system-overview.md).

```mermaid
flowchart TB
    Browser([Browser])

    subgraph OCP["EPFL OpenShift · co2-calculator namespace"]
        Route[Route · TLS edge]
        FE[Frontend<br/>Vue 3 + Quasar SPA<br/>nginx · 2 replicas]
        Docs[Docs<br/>MkDocs · nginx]

        subgraph BE["Backend · FastAPI + Uvicorn · 2 replicas (HPA)"]
            API[API routers<br/>/api/v1/*]
            Auth[Auth<br/>Authlib OIDC · JWT cookies]
            RBAC[Roles & permissions<br/>JWT claims / Accred]
            Ingest[Data ingestion<br/>travel provider]
            FX[Exchange rates<br/>ECB · 8h cache]
            Files[Files<br/>enacit4r-files]
            Audit[Audit sync · OPDo]
            Jobs[Background tasks<br/>asyncio · DB queue · 10s poller]
            ORM[Persistence<br/>SQLAlchemy async]
        end

        Migrate[[Migration Job<br/>alembic upgrade head]]
        DBDump[[db-dump CronJob]]
        Otel[OTEL Collector + Jaeger<br/>via GitOps]
        Cfg[ConfigMap + Secret]
    end

    DB[(PostgreSQL<br/>DBaaS · DSI @ EPFL)]
    PVC[(db-dumps PVC)]
    Entra[(Entra ID)]
    Accred[(Accred)]
    Tableau[(Tableau VizQL)]
    ECB[(ECB API)]
    S3[(EPFL S3)]
    ES[(Elasticsearch)]

    Browser -->|HTTPS| Route
    Route -->|/| FE
    Route -->|/docs| Docs
    Route -->|/api| API
    FE -->|REST · auth cookies| API

    API --> Auth & RBAC & Ingest & FX & Files & Audit & Jobs
    API --> ORM
    Jobs --> ORM
    ORM --> DB
    Migrate --> DB
    DBDump -->|pg_dump| DB
    DBDump --> PVC
    BE -.->|OTLP| Otel
    Auth <-->|OIDC| Entra
    RBAC -.-> Accred
    Ingest -.-> Tableau
    FX -.-> ECB
    Files -.-> S3
    Audit -.-> ES
    Cfg -.-> BE

    classDef fe fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef be fill:#fff8e1,stroke:#e65100,stroke-width:1px
    classDef docs fill:#eceff1,stroke:#546e7a,stroke-width:1px
    classDef edge fill:#e8eaf6,stroke:#3949ab,stroke-width:1px
    classDef cfg fill:#fff8e1,stroke:#f9a825,stroke-width:1px
    classDef mon fill:#ede7f6,stroke:#5e35b1,stroke-width:1px
    classDef data fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef ext fill:#ffebee,stroke:#c62828,stroke-width:1px
    class FE fe
    class Docs docs
    class API,Auth,RBAC,Ingest,FX,Files,Audit,Jobs,ORM be
    class Route edge
    class Migrate,DBDump,Cfg cfg
    class Otel mon
    class DB,PVC data
    class Entra,Accred,Tableau,ECB,S3,ES ext
```

Solid arrows are always-on; dotted arrows are integrations enabled
per-environment through injected secrets (otherwise inert — files fall
back to local disk, audit sync is skipped). The OTEL Collector, Jaeger
and the `db-dump` CronJob are deployed into the namespace via GitOps, not
by the app Helm chart.

## Deployable units

| Unit              | What it is                                                                                                                          |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Frontend**      | Vue 3 + Quasar SPA served by unprivileged Nginx. One app with in-app sections `/app`, `/back-office`, `/system`. 2 replicas.        |
| **Backend**       | FastAPI + Uvicorn (Python 3.12). Auth, business logic, persistence and background jobs in a single process. 2 replicas (HPA 2–10). |
| **Docs**          | This MkDocs site, static, served by Nginx. 1 replica.                                                                              |
| **Migration Job** | Helm hook running `alembic upgrade head` before each release (with a `wait-for-postgres` init).                                     |
| **db-dump CronJob** | Scheduled `pg_dump` of the database to the `db-dumps` PVC (deployed via GitOps).                                                  |

## Backend subsystems

- **API routers** (`/api/v1/*`) — REST surface; HTTP-only auth cookies.
- **Auth** — Authlib OIDC handshake with Entra ID; mints and validates JWT cookies in-process (no separate auth service). See [Auth Flow](./04-auth-flow.md).
- **Roles & permissions** — from JWT claims, or the EPFL Accred API when `PROVIDER_PLUGIN=accred`.
- **Data ingestion** — pluggable providers; the professional-travel provider reads flights from Tableau VizQL.
- **Exchange rates** — pulls FX rates from the ECB API (8-hour in-memory cache).
- **Files** — `enacit4r-files` abstraction; writes to EPFL S3 when configured, otherwise the local filesystem.
- **Audit sync** — ships OPDo audit records to Elasticsearch when configured.
- **Background tasks** — in-process `asyncio` chained via `BackgroundTasks`, backed by a DB job table with a 10-second safety-net poller. No Redis/Celery. See [ADR-010](../architecture-decision-records/010-background-job-processing.md).
- **Persistence** — SQLAlchemy async (psycopg) to a single managed PostgreSQL (EPFL DBaaS); connection pooling is in-process, **no PgBouncer**.
- **Telemetry** — the whole app is OpenTelemetry-instrumented and exports OTLP to the in-namespace OTEL Collector (traces → Jaeger, metrics → Prometheus). See [System Overview](./02-system-overview.md#cross-cutting).

For implementation detail see [Frontend](../frontend/01-overview.md),
[Backend](../backend/01-overview.md) and [Database](../database/01-overview.md).
