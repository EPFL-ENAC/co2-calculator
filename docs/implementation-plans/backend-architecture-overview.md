# Backend Architecture Overview

## Complete System Architecture

```mermaid
graph TB
    subgraph Client["Client Layer"]
        FE[Vue 3 Application]
        Browser[Web Browser]
    end

    subgraph Gateway["API Gateway / Reverse Proxy"]
        NGINX[Nginx]
    end

    subgraph Backend["Backend Services"]
        subgraph FastAPI["FastAPI Application"]
            subgraph Middleware["Middleware Layer"]
                CORS[CORS Handler]
                LOG[Request Logging]
                ERR[Error Handling]
            end

            subgraph Auth["Authentication & Authorization"]
                JWT[JWT Token Validator]
                OAUTH[OAuth2/OIDC Provider]
                POLICY[Policy Engine]
            end

            subgraph API["API Routes v1"]
                AUTH_R[auth.py]
                CR_R[carbon_report.py]
                CM_R[carbon_report_module.py]
                BACK_R[backoffice.py]
                FACT_R[factors.py]
                AUDIT_R[audit.py]
                SYNC_R[data_sync.py]
                FILES_R[files.py]
                LOC_R[locations.py]
                TAX_R[taxonomies.py]
                USER_R[users.py]
                UNIT_R[units.py]
            end

            subgraph Services["Business Logic Layer"]
                AUTH_S[AuthService]
                CR_S[CarbonReportService]
                CM_S[ModuleService]
                BACK_S[BackofficeService]
                FACT_S[FactorService]
                AUDIT_S[AuditService]
                SYNC_S[DataIngestionService]
                FILES_S[FileService]
                LOC_S[LocationService]
                DATA_S[DataEntryService]
                MODULE_H[ModuleHandlerService]
            end

            subgraph Handlers["Module Handlers"]
                HC[HeadcountHandler]
                HT[TravelHandler]
                HE[EquipmentHandler]
                HB[BuildingHandler]
                HP[PurchaseHandler]
                HCLOUD[CloudHandler]
                HAI[AIHandler]
                HPROC[ProcessHandler]
                HRES[ResearchHandler]
            end

            subgraph Repositories["Data Access Layer"]
                USER_REPO[UserRepository]
                UNIT_REPO[UnitRepository]
                CR_REPO[CarbonReportRepo]
                CM_REPO[CarbonReportModuleRepo]
                DATA_REPO[DataEntryRepo]
                FACT_REPO[FactorRepo]
                AUDIT_REPO[AuditRepo]
                INGEST_REPO[IngestionJobRepo]
                LOC_REPO[LocationRepo]
            end

            subgraph Providers["External Providers"]
                S3[S3 Storage Provider]
                OAUTH_P[OAuth Provider]
                FACTOR_P[Factor Data Provider]
            end
        end

        subgraph Tasks["Background Tasks"]
            CELERY[Celery Worker]
            INGEST_TASK[Ingestion Tasks]
            AUDIT_TASK[Audit Sync Tasks]
        end
    end

    subgraph Storage["Data Storage"]
        PG[(PostgreSQL Database)]
        S3_STORE[(S3 File Storage)]
        REDIS[(Redis Cache)]
    end

    subgraph Observability["Observability"]
        OTLP[OpenTelemetry Collector]
        LOKI[Loki Logging]
        PROM[Prometheus Metrics]
        GRAF[Grafana Dashboard]
    end

    Browser --> FE
    FE --> NGINX
    NGINX --> FastAPI

    Middleware --> Auth
    Auth --> API
    API --> Services
    Services --> Handlers
    Services --> Repositories
    Repositories --> PG
    Services --> Providers
    Providers --> S3_STORE

    Services --> Tasks
    Tasks --> PG
    Tasks --> S3_STORE

    FastAPI --> Observability
    Observability --> OTLP
    OTLP --> LOKI
    OTLP --> PROM
    PROM --> GRAF

    style Client fill:#e3f2fd
    style Gateway fill:#fff3e0
    style Backend fill:#f3e5f5
    style Storage fill:#e8f5e9
    style Observability fill:#fce4ec
    style FastAPI fill:#e1f5fe
    style API fill:#bbdefb
    style Services fill:#c8e6c9
    style Repositories fill:#ffe0b2
    style Handlers fill:#f0f4c3
```

## Data Flow by Feature

### 1. User Authentication Flow

```mermaid
sequenceDiagram
    participant Browser
    participant Nginx
    participant FastAPI
    participant OAuth
    participant DB

    Browser->>Nginx: GET /api/v1/auth/login
    Nginx->>FastAPI: Redirect to OAuth
    FastAPI->>OAuth: Initiate OAuth2 flow
    OAuth->>Browser: Login page
    Browser->>OAuth: User credentials
    OAuth->>Browser: Redirect with code
    Browser->>Nginx: GET /callback?code=xxx
    Nginx->>FastAPI: Callback handler
    FastAPI->>OAuth: Exchange code for token
    OAuth->>FastAPI: Access token + user info
    FastAPI->>DB: Upsert user
    DB-->>FastAPI: User record
    FastAPI->>Browser: Set JWT cookie
    Browser->>Nginx: GET /api/v1/auth/me
    Nginx->>FastAPI: Validate JWT
    FastAPI->>DB: Get user details
    DB-->>FastAPI: User profile
    FastAPI-->>Browser: User data
```

### 2. Carbon Report Creation Flow

```mermaid
sequenceDiagram
    participant FE
    participant API
    participant SVC
    participant REPO
    participant DB
    participant AUDIT

    FE->>API: POST /carbon-reports
    API->>SVC: create_report(unit_id, year)
    SVC->>SVC: Validate uniqueness
    SVC->>REPO: insert(report)
    REPO->>DB: INSERT carbon_reports
    DB-->>REPO: report_id
    REPO-->>SVC: created_report
    SVC->>AUDIT: create_audit_log(CREATE, report)
    AUDIT->>DB: INSERT audit_documents
    AUDIT-->>SVC: audit_created
    SVC-->>API: report_data
    API-->>FE: Created report
```

### 3. Module Data Entry Flow

```mermaid
sequenceDiagram
    participant FE
    participant API
    participant SVC
    participant HANDLER
    participant FACTOR_SVC
    participant REPO
    participant DB
    participant AUDIT

    FE->>API: POST /modules/.../items
    API->>SVC: create_item(module_id, data)
    SVC->>HANDLER: get_handler(module_type)
    HANDLER-->>SVC: handler_instance
    SVC->>HANDLER: validate(data)
    HANDLER-->>SVC: validated_data
    SVC->>REPO: insert_data_entry(item)
    REPO->>DB: INSERT data_entries
    DB-->>REPO: item_id
    REPO-->>SVC: created_item
    SVC->>FACTOR_SVC: get_primary_factor(item)
    FACTOR_SVC->>REPO: get_factor(factor_id)
    REPO->>DB: SELECT factors
    DB-->>REPO: factor
    REPO-->>FACTOR_SVC: factor_data
    FACTOR_SVC-->>SVC: factor
    SVC->>HANDLER: calculate_emissions(item, factor)
    HANDLER-->>SVC: emissions_data
    SVC->>REPO: update_emissions(entry_id, emissions)
    REPO->>DB: INSERT data_entry_emissions
    DB-->>REPO: emission_id
    REPO-->>SVC: updated
    SVC->>AUDIT: create_audit_log(CREATE, item)
    AUDIT->>DB: INSERT audit_documents
    AUDIT-->>SVC: audit_created
    SVC-->>API: item_with_emissions
    API-->>FE: Created item
```

### 4. Factor Lookup Flow

```mermaid
sequenceDiagram
    participant FE
    participant API
    participant SVC
    participant REPO
    participant DB

    FE->>API: GET /factors/{type}/classes/{kind}/values
    API->>SVC: get_factor_values(type, kind, subkind)
    SVC->>REPO: query_by_classification(type, kind, subkind)
    REPO->>DB: SELECT factors WHERE...
    DB-->>REPO: factor_record
    REPO-->>SVC: factor
    SVC->>SVC: merge_classification_and_values(factor)
    SVC-->>API: {classification..., values...}
    API-->>FE: Factor data
```

### 5. Backoffice Reporting Flow

```mermaid
sequenceDiagram
    participant FE
    participant API
    participant SVC
    participant REPO
    participant DB

    FE->>API: GET /backoffice/units?years=2024,2025
    API->>SVC: get_reporting_overview(years, filters)
    SVC->>REPO: get_units_with_filters(years, filters)
    REPO->>DB: SELECT units JOIN carbon_reports
    DB-->>REPO: unit_records
    REPO-->>SVC: list[units]

    loop For each unit
        SVC->>REPO: get_carbon_report(unit_id, year)
        REPO->>DB: SELECT carbon_reports
        DB-->>REPO: report
        REPO-->>SVC: report_data

        SVC->>REPO: get_modules(report_id)
        REPO->>DB: SELECT carbon_report_modules
        DB-->>REPO: modules
        REPO-->>SVC: module_list

        loop For each module
            SVC->>REPO: get_data_entries(module_id)
            REPO->>DB: SELECT data_entries
            DB-->>REPO: entries
            REPO-->>SVC: entry_list

            SVC->>REPO: get_emissions(entry_ids)
            REPO->>DB: SELECT data_entry_emissions
            DB-->>REPO: emissions
            REPO-->>SVC: emission_list

            SVC->>SVC: calculate_total(emissions)
        end

        SVC->>SVC: aggregate_unit_stats(unit, modules)
    end

    SVC-->>API: unit_reporting_data
    API-->>FE: Paginated reporting data
```

### 6. Data Ingestion Flow

```mermaid
sequenceDiagram
    participant FE
    participant API
    participant SVC
    participant PROVIDER
    participant REPO
    participant DB
    participant BG

    FE->>API: POST /sync/data-entries/{module_type}
    API->>SVC: create_ingestion_job(payload)
    SVC->>PROVIDER: create_provider(method, config)
    PROVIDER-->>SVC: provider_instance
    SVC->>PROVIDER: validate_connection()
    PROVIDER->>PROVIDER: Connect to source
    PROVIDER-->>SVC: connection_ok
    SVC->>REPO: create_job(payload)
    REPO->>DB: INSERT data_ingestion_jobs
    DB-->>REPO: job_id
    REPO-->>SVC: job_record
    SVC->>BG: schedule_task(job_id)
    BG-->>SVC: task_scheduled
    SVC-->>API: job_status
    API-->>FE: {"job_id": 123, "status": "pending"}

    Note over BG,DB: Background processing
    BG->>PROVIDER: fetch_data()
    PROVIDER->>PROVIDER: Parse source data
    PROVIDER-->>BG: data_records

    loop For each record
        BG->>SVC: transform_record(record)
        SVC->>PROVIDER: map_to_model(record)
        PROVIDER-->>SVC: model_data
        SVC->>REPO: upsert_data_entry(model)
        REPO->>DB: INSERT/UPDATE data_entries
        DB-->>REPO: success
        REPO-->>SVC: saved
        BG->>REPO: update_job_progress(job_id, progress)
        REPO->>DB: UPDATE jobs
    end

    BG->>REPO: mark_job_completed(job_id)
    REPO->>DB: UPDATE jobs SET status=COMPLETED
    DB-->>REPO: updated
```

## Component Interaction Map

```mermaid
graph LR
    subgraph Routes["API Routes"]
        R1[auth.py]
        R2[carbon_report.py]
        R3[carbon_report_module.py]
        R4[backoffice.py]
        R5[factors.py]
        R6[audit.py]
        R7[data_sync.py]
    end

    subgraph Services["Services"]
        S1[AuthService]
        S2[CarbonReportService]
        S3[ModuleService]
        S4[BackofficeService]
        S5[FactorService]
        S6[AuditService]
        S7[DataIngestionService]
    end

    subgraph Repositories["Repositories"]
        RE1[UserRepo]
        RE2[CarbonReportRepo]
        RE3[ModuleRepo]
        RE4[UnitRepo]
        RE5[FactorRepo]
        RE6[AuditRepo]
        RE7[IngestionRepo]
    end

    R1 --> S1
    R2 --> S2
    R3 --> S3
    R4 --> S4
    R5 --> S5
    R6 --> S6
    R7 --> S7

    S1 --> RE1
    S2 --> RE2
    S3 --> RE3
    S4 --> RE4
    S5 --> RE5
    S6 --> RE6
    S7 --> RE7

    style Routes fill:#bbdefb
    style Services fill:#c8e6c9
    style Repositories fill:#ffe0b2
```

## Technology Stack

```mermaid
graph TB
    subgraph Frontend["Frontend"]
        V[Vue 3]
        Q[Quasar Framework]
        T[TypeScript]
        P[Pinia State]
        K[ky HTTP Client]
    end

    subgraph Backend["Backend"]
        F[FastAPI]
        PY[Python 3.12]
        SQL[SQLModel/SQLAlchemy]
        PD[Pydantic]
        R[Ruff]
        M[Mypy]
    end

    subgraph Database["Database"]
        PG[PostgreSQL]
        A[asyncpg Driver]
    end

    subgraph Auth["Authentication"]
        O[Authlib OAuth2]
        J[joserfc JWT]
    end

    subgraph Infra["Infrastructure"]
        D[Docker]
        K8[Kubernetes]
        H[Helm Charts]
    end

    subgraph Observ["Observability"]
        OT[OpenTelemetry]
        L[Loki]
        PR[Prometheus]
    end

    V --> Q
    Q --> T
    T --> P
    T --> K

    PY --> F
    F --> SQL
    F --> PD
    PY --> R
    PY --> M

    SQL --> PG
    PG --> A

    F --> O
    O --> J

    D --> K8
    K8 --> H

    F --> OT
    OT --> L
    OT --> PR

    style Frontend fill:#e3f2fd
    style Backend fill:#f3e5f5
    style Database fill:#e8f5e9
    style Auth fill:#fff3e0
    style Infra fill:#fce4ec
    style Observ fill:#e0f2f1
```

## Deployment Architecture

```mermaid
graph TB
    subgraph Cloud["Cloud Infrastructure"]
        subgraph K8s["Kubernetes Cluster"]
            subgraph Namespace["co2-calculator namespace"]
                subgraph Backend["Backend Deployment"]
                    BE1[Backend Pod 1]
                    BE2[Backend Pod 2]
                    BE3[Backend Pod 3]
                end

                subgraph Frontend["Frontend Deployment"]
                    FE1[Frontend Pod 1]
                    FE2[Frontend Pod 2]
                end

                subgraph Services["Services"]
                    SV1[Service: Backend]
                    SV2[Service: Frontend]
                end

                subgraph Ingress["Ingress Controller"]
                    IN[Ingress Resource]
                end
            end
        end

        subgraph External["External Services"]
            DB[(Cloud SQL PostgreSQL)]
            S3[(Cloud Storage)]
            OAUTH[OAuth Provider]
        end

        subgraph Monitoring["Monitoring"]
            LO[Loki]
            PR[Prometheus]
            GR[Grafana]
        end
    end

    User((Users)) --> IN
    IN --> SV2
    IN --> SV1
    SV2 --> FE1
    SV2 --> FE2
    SV1 --> BE1
    SV1 --> BE2
    SV1 --> BE3
    BE1 --> DB
    BE2 --> DB
    BE3 --> DB
    BE1 --> S3
    BE2 --> S3
    BE3 --> S3
    BE1 --> OAUTH
    BE2 --> OAUTH
    BE3 --> OAUTH

    BE1 --> LO
    BE2 --> LO
    BE3 --> LO
    BE1 --> PR
    BE2 --> PR
    BE3 --> PR
    PR --> GR

    style Cloud fill:#f5f5f5
    style K8s fill:#e3f2fd
    style Backend fill:#bbdefb
    style Frontend fill:#c8e6c9
    style Services fill:#fff9c4
    style Ingress fill:#ffcc80
    style External fill:#f8bbd0
    style Monitoring fill:#e1bee7
```

## Security Architecture

```mermaid
graph TB
    subgraph Security["Security Layers"]
        subgraph Network["Network Security"]
            FW[Firewall Rules]
            VPC[VPC Network]
            SSL[SSL/TLS Termination]
        end

        subgraph AuthN["Authentication"]
            OAUTH[OAuth2/OIDC]
            JWT[JWT Tokens]
            COOK[Secure Cookies]
        end

        subgraph AuthZ["Authorization"]
            POL[Policy Engine]
            RBAC[Role-Based Access]
            PERM[Permission Checks]
        end

        subgraph Data["Data Security"]
            ENC[Encryption at Rest]
            TRANS[Encryption in Transit]
            AUD[Audit Logging]
        end
    end

    User((User)) --> FW
    FW --> VPC
    VPC --> SSL
    SSL --> OAUTH
    OAUTH --> JWT
    JWT --> COOK
    COOK --> POL
    POL --> RBAC
    RBAC --> PERM
    PERM --> APP[Application]
    APP --> ENC
    ENC --> TRANS
    TRANS --> AUD

    style Security fill:#ffebee
    style Network fill:#ffcdd2
    style AuthN fill:#ef9a9a
    style AuthZ fill:#e57373
    style Data fill:#f44336
```
