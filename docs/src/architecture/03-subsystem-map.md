# Subsystem Map

- Basic communication between component

```mermaid
graph TD
    %% Layers
    FE[Frontend]
    BE[Backend]
    WK[Workers]
    DB[Database]
    ST[Storage]

    %% Main Flow
    FE -->|HTTP REST API| BE
    BE -->|Message Queue| WK
    BE -->|SQLAlchemy ORM| DB
    BE -->|API Calls| ST
    WK -->|Optional DB Access| DB
    WK -->|Optional Storage Access| ST

    %% Bidirectional Arrows
    FE <--> BE
    BE <--> WK
```

- Detailed mermaid graph

```mermaid
graph TD
    %% External / Load Balancer
    LB[Load Balancer]
    User[User]
    EntraID[EntraID]
    S3[S3]

    %% Ingress
    Ingress[Ingress]

    %% Routes
    Root[Root]
    API[API]
    Docs[Docs]
    ITMgr[IT Manager Route]
    TeamMgr[Team Manager Route]

    %% Frontend Apps
    SPA[SPA Frontend]
    ITApp[IT App Frontend]
    TeamApp[Team App Frontend]

    %% Backend
    FastAPI1[FastAPI1]
    FastAPI2[FastAPI2]
    APIAuth[API Auth]

    %% Workers
    Redis[Redis]
    Celery1[Celery1]
    Celery2[Celery2]

    %% Database
    PGBouncer1[PGBouncer1]
    PGBouncer2[PGBouncer2]
    Primary[Primary DB]
    Replica1[Replica1 DB]
    Replica2[Replica2 DB]

    %% Config / Monitoring
    DBCreds[DB Credentials]
    ConfigMaps[Config Maps]
    Prometheus[Prometheus]
    Grafana[Grafana]

    %% --- Connections ---
    %% Users flow
    User -->|HTTP / HTTPS| LB
    LB --> Ingress
    Ingress --> Root
    Ingress --> API
    Ingress --> Docs
    Ingress --> ITMgr
    Ingress --> TeamMgr

    %% Routes to frontends
    Root --> SPA
    ITMgr --> ITApp
    TeamMgr --> TeamApp
    API --> FastAPI1
    API --> FastAPI2
    API --> APIAuth

    %% Backend to workers
    FastAPI1 --> Celery1
    FastAPI2 --> Celery2
    APIAuth --> Redis
    FastAPI1 --> Redis
    FastAPI2 --> Redis

    %% Backend to Database via PGBouncer
    FastAPI1 --> PGBouncer1
    FastAPI2 --> PGBouncer2
    APIAuth --> PGBouncer1
    PGBouncer1 --> Primary
    PGBouncer1 --> Replica1
    PGBouncer2 --> Primary
    PGBouncer2 --> Replica2

    %% Workers optional DB/Storage access
    Celery1 --> Primary
    Celery2 --> Replica2
    Celery1 --> S3
    Celery2 --> S3

    %% Config & Monitoring
    FastAPI1 --> ConfigMaps
    FastAPI2 --> ConfigMaps
    APIAuth --> DBCreds
    Prometheus --> FastAPI1
    Prometheus --> FastAPI2
    Prometheus --> Celery1
    Prometheus --> Celery2
    Grafana --> Prometheus

    %% External Identity & Storage
    SPA --> EntraID
    ITApp --> EntraID
    TeamApp --> EntraID

```

The system follows a layered architecture pattern with clear separation of concerns between different subsystems.

## Layer Dependencies

```
Frontend ↔ Backend ↔ Workers ↔ DB
                ↕
            Storage
```

Each layer communicates with adjacent layers through well-defined interfaces:

- Frontend communicates with Backend via HTTP REST APIs
- Backend communicates with Workers via message queues
- Backend communicates with Database via SQLAlchemy ORM
- Backend communicates with Storage via direct API calls
- Workers may communicate with Database and Storage as needed

For implementation details, see:

- [Frontend Documentation](../frontend/index.md)
- [Backend Documentation](../backend/index.md)
- [Database Documentation](../database/index.md)
- [Storage Documentation](../backend/architecture.md)
