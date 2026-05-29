# Subsystem Map

- Basic communication between component

```mermaid
graph TD
    %% Layers
    FE[Frontend]
    BE[Backend]
    DB[Database]
    ST[Storage]

    %% Main Flow
    FE -->|HTTP REST API| BE
    BE -->|SQLAlchemy ORM| DB
    BE -->|API Calls| ST

    %% Bidirectional Arrows
    FE <--> BE
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

    %% Backend to Database via PGBouncer
    FastAPI1 --> PGBouncer1
    FastAPI2 --> PGBouncer2
    APIAuth --> PGBouncer1
    PGBouncer1 --> Primary
    PGBouncer1 --> Replica1
    PGBouncer2 --> Primary
    PGBouncer2 --> Replica2

    %% Backend in-process Storage access (background jobs run in-process via asyncio)
    FastAPI1 --> S3
    FastAPI2 --> S3

    %% Config & Monitoring
    FastAPI1 --> ConfigMaps
    FastAPI2 --> ConfigMaps
    APIAuth --> DBCreds
    Prometheus --> FastAPI1
    Prometheus --> FastAPI2
    Grafana --> Prometheus

    %% External Identity & Storage
    SPA --> EntraID
    ITApp --> EntraID
    TeamApp --> EntraID

```

The system follows a layered architecture pattern with clear separation of concerns between different subsystems.

## Layer Dependencies

```
Frontend ↔ Backend ↔ DB
               ↕
           Storage
```

Each layer communicates with adjacent layers through well-defined interfaces:

- Frontend communicates with Backend via HTTP REST APIs
- Backend communicates with Database via SQLAlchemy ORM
- Backend communicates with Storage via direct API calls
- Background jobs run in-process inside the Backend (asyncio, no external task queue)

For implementation details, see:

- [Frontend Documentation](../frontend/01-overview.md)
- [Backend Documentation](../backend/01-overview.md)
- [Database Documentation](../database/01-overview.md)
- [Storage Documentation](../backend/01-overview.md)
