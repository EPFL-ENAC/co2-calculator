# Deployment Topology

This document describes the infrastructure topology for local, staging,
and production environments.

## Docker Compose (Local/Staging)

Local development uses Docker Compose for simplified service
orchestration.

```mermaid
graph TB
    subgraph "Docker Compose Network"
        Frontend[Frontend Container<br/>Port 3000]
        Backend[Backend Container<br/>Port 8000]
        DB[(PostgreSQL<br/>Port 5432)]
        Redis[(Redis<br/>Port 6379)]
        Worker[Celery Worker]
        Storage[MinIO/S3<br/>Port 9000]

        Frontend -->|HTTP| Backend
        Backend -->|SQL| DB
        Backend -->|Tasks| Redis
        Redis -->|Jobs| Worker
        Worker -->|SQL| DB
        Worker -->|Files| Storage
        Backend -->|Files| Storage
    end

    User[Developer] -->|localhost:3000| Frontend

    style Frontend fill:#e1f5ff
    style Backend fill:#fff4e1
    style DB fill:#e1ffe1
    style Redis fill:#ffe1e1
    style Worker fill:#f5e1ff
    style Storage fill:#ffe1f5
```

**Key characteristics:**

- Single docker-compose.yml file
- Shared network for service communication
- Volume mounts for data persistence
- Hot reload for development

## Kubernetes Cluster (Production)

Production deployments use Kubernetes for scalability and reliability.

```mermaid
graph TB
    subgraph "External"
        User[Users]
        LB[EPFL Load Balancer]
    end

    subgraph "Kubernetes Cluster"
        Ingress[NGINX Ingress Controller]

        subgraph "Frontend Namespace"
            FE1[Frontend Pod 1]
            FE2[Frontend Pod 2]
            FESvc[Frontend Service]
        end

        subgraph "Backend Namespace"
            BE1[Backend Pod 1]
            BE2[Backend Pod 2]
            BESvc[Backend Service]
        end

        subgraph "Worker Namespace"
            W1[Worker Pod 1]
            W2[Worker Pod 2]
            Redis[(Redis)]
        end

        subgraph "Data Namespace"
            PG[(PostgreSQL Primary)]
            PGR[(PostgreSQL Replica)]
            PGB[PgBouncer]
        end

        subgraph "Monitoring"
            Prom[Prometheus]
            Graf[Grafana]
        end
    end

    subgraph "External Services"
        S3[Azure Blob Storage]
        Entra[Microsoft Entra ID]
    end

    User -->|HTTPS| LB
    LB --> Ingress
    Ingress --> FESvc
    FESvc --> FE1 & FE2
    FE1 & FE2 --> BESvc
    BESvc --> BE1 & BE2
    BE1 & BE2 --> PGB
    BE1 & BE2 --> Redis
    BE1 & BE2 --> S3
    Redis --> W1 & W2
    W1 & W2 --> PGB
    W1 & W2 --> S3
    PGB --> PG
    PGB --> PGR
    PG -->|Replication| PGR

    FE1 & FE2 --> Entra
    BE1 & BE2 --> Entra

    Prom --> BE1 & BE2
    Prom --> W1 & W2
    Graf --> Prom

    style User fill:#e1f5ff
    style LB fill:#ffe1e1
    style Ingress fill:#fff4e1
    style FESvc fill:#e1f5ff
    style BESvc fill:#fff4e1
    style PG fill:#e1ffe1
    style Redis fill:#ffe1e1
```

**Key characteristics:**

- Helm charts for service deployment
- ArgoCD for GitOps deployment management
- Ingress controllers for external access
- Horizontal pod autoscaling
- Rolling updates with zero downtime

### Service Mesh Overview

Currently not using a service mesh, but may adopt Istio in the future for:

- Enhanced observability
- Traffic management
- Security policies

### Ingress and Networking Patterns

```mermaid
graph LR
    subgraph "External Traffic"
        Internet[Internet]
        EPFLLB[EPFL Load Balancer]
    end

    subgraph "Kubernetes Ingress"
        Ingress[NGINX Ingress<br/>TLS Termination]
    end

    subgraph "Application Routes"
        Root[/ → Frontend SPA]
        API[/api → Backend]
        Docs[/docs → Documentation]
        ITMgr[/it-manager → IT App]
        TeamMgr[/team-manager → Team App]
    end

    Internet -->|HTTPS| EPFLLB
    EPFLLB -->|HTTPS| Ingress
    Ingress --> Root
    Ingress --> API
    Ingress --> Docs
    Ingress --> ITMgr
    Ingress --> TeamMgr

    style Internet fill:#e1f5ff
    style EPFLLB fill:#ffe1e1
    style Ingress fill:#fff4e1
    style Root fill:#e1f5ff
    style API fill:#e1ffe1
```

**Networking features:**

- EPFL load balancer for external access
- NGINX ingress controller for HTTP routing
- TLS termination at ingress level
- Network policies for service isolation
- Path-based routing to services

For detailed deployment information, see [Infrastructure Documentation](../infra/01-overview.md).
