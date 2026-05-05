---
status: delivered
last_updated: 2026-05-05
summary: System-context and container view of co2-calculator.
---

# System Overview

This page gives a C4-style **context** and **container** view of the
co2-calculator. It answers: *who uses it, what it depends on, and which
deployable units make it up.*

For deeper detail, jump to:

- [Subsystem Map](./03-subsystem-map.md) — internal component graph
- [Data Flow](./10-data-flow.md) — request and upload sequences
- [Tech Stack](./08-tech-stack.md) — frameworks and versions
- [Deployment Topology](./11-deployment-topology.md) — Kubernetes layout

---

## System Context

Actors and external dependencies surrounding the system.

```mermaid
flowchart LR
    User([EPFL User])
    Admin([IT / Team Admin])
    System["co2-calculator<br/>(SPA + API)"]
    Entra[(Microsoft Entra ID<br/>OAuth2 / OIDC)]
    S3[(EPFL S3<br/>Object Storage)]

    User -->|Browse, upload, view reports| System
    Admin -->|Manage users, units, factors| System
    System <-->|Authenticate| Entra
    System <-->|Files and exports| S3

    classDef system fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef ext fill:#ffebee,stroke:#c62828,stroke-width:2px
    class System system
    class Entra,S3 ext
```

**Boundaries.** The system owns its data (PostgreSQL, which also stores
the background-job queue table). Identity is delegated to Entra ID. File
blobs live in EPFL S3. Everything else is internal.

---

## Containers

Deployable units inside the Kubernetes cluster and their main
collaborators.

```mermaid
flowchart TB
    Browser([Browser])

    subgraph Edge["Edge"]
        Ingress[nginx-ingress<br/>TLS via cert-manager]
    end

    subgraph K8s["Kubernetes (EPFL XaaS)"]
        FE["Frontend<br/>Vue 3 + Quasar (Nginx)"]
        BE["Backend API<br/>FastAPI + Uvicorn<br/>(in-process background tasks)"]
        PG[(PostgreSQL<br/>via PgBouncer)]
    end

    Entra[(Entra ID)]
    S3[(EPFL S3)]

    Browser -->|HTTPS| Ingress
    Ingress -->|/| FE
    Ingress -->|/api| BE
    FE -->|REST / JSON<br/>auth cookies| BE
    BE <-->|OIDC| Entra
    BE -->|SQLAlchemy async| PG
    BE <-->|read/write blobs| S3

    classDef fe fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef be fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef data fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef ext fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef edge fill:#e8eaf6,stroke:#3949ab,stroke-width:2px

    class FE fe
    class BE be
    class PG data
    class Entra,S3 ext
    class Ingress edge
```

### Container responsibilities

| Container           | Role                                                                                                                |
| ------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Frontend**        | Static SPA bundle, Quasar UI, calls Backend over REST with HTTP-only auth cookies.                                  |
| **Backend API**     | Auth, business logic, persistence, file uploads via `/files/temp-upload`.                                           |
| **Background tasks**| In-process FastAPI `BackgroundTasks` chained via `asyncio.create_task`; 10s safety-net poller. See ADR-010.         |
| **PostgreSQL**      | System of record (also holds the background-job queue table), accessed via PgBouncer.                               |

Stack and versions live in [Tech Stack](./08-tech-stack.md).

---

## Request Lifecycle (high level)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL

    U->>FE: Action (e.g. upload CSV)
    FE->>BE: REST + auth cookie
    BE->>DB: Persist metadata + claim job
    BE-->>FE: 202 + job id
    Note over BE: asyncio.create_task chain
    BE->>DB: Write results
    FE->>BE: Poll status (or SSE)
    BE->>DB: Read status
    BE-->>FE: Result / progress
```

Detailed sequences (uploads, exports, auth) are in
[Data Flow](./10-data-flow.md) and [Auth Flow](./04-auth-flow.md).

---

## Cross-cutting

- **Identity.** Entra ID OIDC handshake exchanged for HTTP-only
  `auth_token` / `refresh_token` cookies — see
  [Auth Flow](./04-auth-flow.md).
- **Observability.** Prometheus scrapes Backend + PgBouncer; Grafana
  dashboards in cluster.
- **Config.** ConfigMaps + Secrets per environment — see
  [Environments](./05-environments.md).
- **Scaling.** Stateless API (and its in-process tasks) scales via HPA —
  see [Scalability](./12-scalability.md).
