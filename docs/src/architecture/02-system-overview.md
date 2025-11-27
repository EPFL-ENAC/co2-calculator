# System Overview Diagram

- Interaction component Basic

```mermaid
graph TB
    User([User/Browser])
    LB[EPFL Load Balancer]

    subgraph K8S["Kubernetes Cluster (XaaS Platform)"]
        Ingress[Ingress Controller]

        subgraph Routes["Route Definitions"]
            Root["/ → SPA"]
            API["/api → Backend"]
            Docs["/docs → API Docs"]
            ITMgr["/it-manager → IT UI"]
            TeamMgr["/team-manager → Team UI"]
        end

        Frontend[Frontend Pods<br/>Vue 3 Applications]
        Backend[Backend Pods<br/>FastAPI Services]
        Workers[Worker Pods<br/>Celery + Redis]
        Database[Database Layer<br/>PostgreSQL + PgBouncer]
    end

    subgraph External["External Services"]
        Auth[Microsoft Entra ID<br/>OAuth2/OIDC]
        S3[EPFL S3 Storage]
    end

    User -->|HTTPS| LB
    LB --> Ingress
    Ingress --> Routes
    Routes --> Frontend
    Routes --> Backend

    Frontend -->|API Calls| Backend
    Backend <-->|Authentication| Auth
    Backend -->|Read/Write| Database
    Backend -->|Enqueue Tasks| Workers
    Backend <-->|Files| S3

    Workers -->|Read/Write| Database
    Workers <-->|Files| S3

    classDef external fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef ingress fill:#e8eaf6,stroke:#3949ab,stroke-width:2px
    classDef route fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef frontend fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef workers fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef database fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px

    class User,LB external
    class Ingress ingress
    class Root,API,Docs,ITMgr,TeamMgr route
    class Frontend frontend
    class Backend backend
    class Workers workers
    class Database database
    class Auth,S3 external
```

- Interaction component detailed

```mermaid
graph TB
    User([User/Browser])
    LB[EPFL Load Balancer]

    subgraph K8S["Kubernetes Cluster (XaaS Platform)"]
        Ingress[Ingress Controller]

        subgraph Routes["Ingress Definitions"]
            Root["/ - SPA Frontend"]
            API["/api - Backend REST"]
            Docs["/docs - Public API Docs"]
            ITMgr["/it-manager - IT Interface"]
            TeamMgr["/team-manager - Team Interface"]
        end

        subgraph Frontend["Frontend Pods"]
            SPA[Vue 3 SPA]
            ITApp[IT Manager App]
            TeamApp[Team Manager App]
        end

        subgraph AppLayer["Application Layer"]
            subgraph Backend["Backend Pods"]
                FastAPI1[FastAPI Pod 1]
                FastAPI2[FastAPI Pod 2]
                APIAuth[Auth Middleware]
            end

            subgraph Workers["Worker Pods"]
                Redis[Redis Queue]
                Celery1[Celery Worker 1]
                Celery2[Celery Worker 2]
            end
        end

        subgraph DatabaseLayer["Database Layer"]
            subgraph Pooling["Connection Pooling"]
                PGBouncer1[PgBouncer Primary]
                PGBouncer2[PgBouncer Secondary]
            end

            subgraph PostgreSQL["PostgreSQL Cluster"]
                Primary[(PostgreSQL Primary<br/>Read/Write)]
                Replica1[(PostgreSQL Replica 1<br/>Read Only)]
                Replica2[(PostgreSQL Replica 2<br/>Read Only)]
            end
        end

        subgraph Config["Config & Secrets"]
            DBCreds[DB Credentials]
            ConfigMaps[ConfigMaps]
        end

        subgraph Monitoring["Monitoring & Observability"]
            Prometheus[Prometheus]
            Grafana[Grafana]
        end
    end

    subgraph External["External Services"]
        EntraID[Microsoft Entra ID<br/>OAuth2/OpenID Connect]
        S3[EPFL S3 Storage<br/>Object Storage]
    end

    User -->|HTTPS| LB
    LB -->|Route Traffic| Ingress

    Ingress -->|/* catch-all| Root
    Ingress -->|/api/*| API
    Ingress -->|/docs| Docs
    Ingress -->|/it-manager/*| ITMgr
    Ingress -->|/team-manager/*| TeamMgr

    Root -->|Serve| SPA
    ITMgr -->|Serve| ITApp
    TeamMgr -->|Serve| TeamApp

    API -->|Forward| FastAPI1
    API -->|Forward| FastAPI2
    Docs -->|Swagger UI| FastAPI1

    SPA -->|API Calls| FastAPI1
    ITApp -->|API Calls| FastAPI1
    TeamApp -->|API Calls| FastAPI2

    FastAPI1 -->|Authenticate| APIAuth
    FastAPI2 -->|Authenticate| APIAuth
    APIAuth <-->|OAuth2/OIDC| EntraID

    FastAPI1 -->|Enqueue Jobs| Redis
    FastAPI2 -->|Enqueue Jobs| Redis

    FastAPI1 -->|Read/Write Queries| PGBouncer1
    FastAPI2 -->|Read/Write Queries| PGBouncer1

    Redis -->|Distribute| Celery1
    Redis -->|Distribute| Celery2

    Celery1 -->|Read/Write Queries| PGBouncer2
    Celery2 -->|Read/Write Queries| PGBouncer2

    FastAPI1 <-->|Store/Retrieve Files| S3
    FastAPI2 <-->|Store/Retrieve Files| S3
    Celery1 <-->|Read/Write Files| S3
    Celery2 <-->|Read/Write Files| S3

    PGBouncer1 -->|Writes| Primary
    PGBouncer1 -->|Reads| Replica1
    PGBouncer1 -->|Reads| Replica2

    PGBouncer2 -->|Writes| Primary
    PGBouncer2 -->|Reads| Replica1
    PGBouncer2 -->|Reads| Replica2

    Primary -.->|Replication| Replica1
    Primary -.->|Replication| Replica2

    DBCreds --> FastAPI1
    DBCreds --> FastAPI2
    DBCreds --> Celery1
    DBCreds --> Celery2
    DBCreds --> PGBouncer1
    DBCreds --> PGBouncer2

    ConfigMaps --> FastAPI1
    ConfigMaps --> FastAPI2

    Prometheus --> FastAPI1
    Prometheus --> FastAPI2
    Prometheus --> PGBouncer1
    Prometheus --> PGBouncer2
    Grafana --> Prometheus

    classDef external fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef ingress fill:#e8eaf6,stroke:#3949ab,stroke-width:2px
    classDef frontend fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef workers fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef database fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef config fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef route fill:#fff9c4,stroke:#f57f17,stroke-width:2px

    class User,LB external
    class Ingress ingress
    class Root,API,Docs,ITMgr,TeamMgr route
    class SPA,ITApp,TeamApp frontend
    class FastAPI1,FastAPI2,APIAuth backend
    class Redis,Celery1,Celery2 workers
    class PGBouncer1,PGBouncer2,Primary,Replica1,Replica2 database
    class DBCreds,ConfigMaps,Prometheus,Grafana config
    class EntraID,S3 external
```

- Interaction component less detailed

```mermaid
graph TB
    Frontend["Frontend Layer<br/>Vue 3 + Quasar"]
    Backend["Backend Layer<br/>FastAPI"]
    Workers["Workers Layer<br/>Celery + Redis"]
    Database["Database Layer<br/>PostgreSQL"]
    Storage["Storage Layer<br/>EPFL S3"]
    Infra["Infrastructure Layer<br/>Kubernetes on XaaS"]

    Frontend <-->|REST API| Backend
    Backend <-->|Enqueue Tasks| Workers
    Backend <-->|Read/Write| Database
    Backend <-->|Upload/Download| Storage
    Workers -->|Read/Write Files| Storage
    Workers -->|Store Results| Database
    Infra -.->|Hosts| Frontend
    Infra -.->|Hosts| Backend
    Infra -.->|Hosts| Workers
    Infra -.->|Manages| Database
    Infra -.->|Manages| Storage

    classDef frontend fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef workers fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef database fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef storage fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef infra fill:#fce4ec,stroke:#880e4f,stroke-width:2px

    class Frontend frontend
    class Backend backend
    class Workers workers
    class Database database
    class Storage storage
    class Infra infra
```

- Overview of database query system

```mermaid
flowchart TD
    subgraph K8s Cluster
        A[FastAPI Pods] -->|Read/Write Queries| B[PgBouncer Primary/Secondary]
        B -->|Writes| C[(PostgreSQL Primary)]
        B -->|Reads| D[(PostgreSQL Replica 1)]
        B -->|Reads| E[(PostgreSQL Replica 2)]
    end

    subgraph Config & Secrets
        F[DB Credentials & ConfigMaps] --> A
        F --> B
    end

    subgraph Monitoring & Observability
        G[Prometheus / Grafana] --> A
        G --> B
    end
```

- Dataflow

```mermaid
graph TB
    User([User])
    FE[Frontend]
    BE[Backend API]
    Queue[Redis Queue]
    Worker[Celery Workers]
    Process[Process]
    DB[(PostgreSQL)]
    S3[(S3 Storage)]

    User -->|1. Upload File| FE
    FE -->|2. POST Request| BE
    BE -->|3. Store File| S3
    BE -->|4. Create Task| Queue
    BE -->|5. Save Metadata| DB
    Queue -->|6. Dispatch| Worker
    Worker -->|7. Fetch File| S3
    Worker -->|8. Process| Process
    Process -->|8.a result |Worker
    Worker -->|9. Store Results| DB
    Worker -->|10. Save Output| S3
    BE -->|11. Response| FE
    FE -->|12. Display| User

    classDef userStyle fill:#e0e0e0,stroke:#424242,stroke-width:2px
    classDef frontendStyle fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef backendStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef workerStyle fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef dataStyle fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef storageStyle fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef ProcessStyle fill:#ffeeff,stroke:#f13f4a,stroke-width:2px

    class User userStyle
    class FE frontendStyle
    class BE backendStyle
    class Queue,Worker workerStyle
    class DB dataStyle
    class S3 storageStyle
    class Process ProcessStyle
```

The system consists of several interconnected layers that work together to provide the complete functionality. The diagram above shows the high-level components and their interactions.

## High-Level Components

1. **Frontend Layer** - User interface implemented with Vue 3 and Quasar
2. **Backend Layer** - RESTful API implemented with FastAPI
3. **Workers Layer** - Asynchronous processing with Celery and Redis
4. **Database Layer** - Data persistence with PostgreSQL
5. **Storage Layer** - Object storage for file uploads
6. **Infrastructure Layer** - Hosting and operational components

For detailed information about each component, see the Component Breakdown section below and the specific documentation in the corresponding folders under `docs/`.
