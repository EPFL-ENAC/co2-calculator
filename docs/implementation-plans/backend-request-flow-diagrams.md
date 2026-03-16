# Backend Request Flow Diagrams

This document contains Mermaid diagrams illustrating the request flow from frontend to backend for major endpoint categories.

## 1. Authentication Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as API Router
    participant AUTH as Auth Service
    participant DB as Database
    participant JWT as JWT Token

    FE->>API: GET /api/v1/auth/me
    API->>AUTH: validate_token()
    AUTH->>JWT: decode_token(token)
    JWT-->>AUTH: user_data
    AUTH->>DB: query_user(user_id)
    DB-->>AUTH: user_record
    AUTH-->>API: user_info
    API-->>FE: User profile data
```

## 2. Carbon Reports Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as carbon_report Router
    participant SVC as CarbonReportService
    participant REPO as CarbonReportRepo
    participant DB as Database

    FE->>API: GET /api/v1/carbon-reports/unit/{unit_id}/
    API->>SVC: list_reports(unit_id)
    SVC->>REPO: query_by_unit(unit_id)
    REPO->>DB: SELECT * FROM carbon_reports WHERE unit_id=?
    DB-->>REPO: report_records
    REPO-->>SVC: list[CarbonReport]
    SVC-->>API: report_data
    API-->>FE: JSON response

    Note over FE,DB: Create new report
    FE->>API: POST /api/v1/carbon-reports/
    API->>SVC: create_report(payload)
    SVC->>REPO: insert(report)
    REPO->>DB: INSERT INTO carbon_reports...
    DB-->>REPO: new_id
    REPO-->>SVC: created_report
    SVC-->>API: report_data
    API-->>FE: Created report
```

## 3. Modules Data Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as carbon_report_module Router
    participant SVC as ModuleService
    participant REPO as ModuleRepo
    participant DB as Database

    FE->>API: GET /api/v1/modules/{unit_id}/{year}/{module_id}
    API->>SVC: get_module_data(module_id)
    SVC->>REPO: get_by_id(module_id)
    REPO->>DB: SELECT * FROM carbon_report_modules WHERE id=?
    DB-->>REPO: module_record
    REPO-->>SVC: module_data
    SVC->>SVC: calculate_stats(module_data)
    SVC-->>API: module_with_stats
    API-->>FE: Module data with equipment/emissions

    Note over FE,DB: Create module item
    FE->>API: POST /api/v1/modules/{unit_id}/{year}/{module_id}/items
    API->>SVC: create_item(module_id, data)
    SVC->>REPO: insert_data_entry(item)
    REPO->>DB: INSERT INTO data_entries...
    DB-->>REPO: new_id
    REPO-->>SVC: created_item
    SVC->>SVC: validate_and_calculate(item)
    SVC-->>API: item_with_emissions
    API-->>FE: Created item
```

## 4. Factors Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as factors Router
    participant SVC as FactorService
    participant REPO as FactorRepo
    participant DB as Database

    FE->>API: GET /api/v1/factors/{submodule}/class-subclass-map
    API->>SVC: get_class_subclass_map(data_entry_type)
    SVC->>REPO: query_by_classification(type, kind)
    REPO->>DB: SELECT * FROM factors WHERE...
    DB-->>REPO: factor_records
    REPO-->>SVC: list[factors]
    SVC->>SVC: build_classification_map(factors)
    SVC-->>API: class_subclass_map
    API-->>FE: Classification map

    Note over FE,DB: Get factor values
    FE->>API: GET /api/v1/factors/{submodule}/classes/{kind}/values
    API->>SVC: get_factor_values(data_entry_type, kind, subkind)
    SVC->>REPO: get_by_classification(type, kind, subkind)
    REPO->>DB: SELECT * FROM factors WHERE...
    DB-->>REPO: factor_record
    REPO-->>SVC: factor
    SVC->>SVC: merge_classification_and_values(factor)
    SVC-->>API: factor_data
    API-->>FE: Factor values
```

## 5. Backoffice Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as backoffice Router
    participant SVC as BackofficeService
    participant REPO as UnitRepo
    participant DB as Database

    FE->>API: GET /api/v1/backoffice/units
    API->>SVC: get_reporting_overview(years, filters)
    SVC->>REPO: get_units_with_filters(years, filters)
    REPO->>DB: SELECT * FROM units JOIN carbon_reports...
    DB-->>REPO: unit_records
    REPO-->>SVC: list[units]
    SVC->>SVC: calculate_footprints(units)
    SVC-->>API: unit_reporting_data
    API-->>FE: Paginated unit data

    Note over FE,DB: Get unit details
    FE->>API: GET /api/v1/backoffice/unit/{unit_id}
    API->>SVC: get_unit_details(unit_id)
    SVC->>REPO: get_by_id(unit_id)
    REPO->>DB: SELECT * FROM units WHERE id=?
    DB-->>REPO: unit_record
    REPO-->>SVC: unit_data
    SVC->>SVC: get_reporting_summary(unit_id)
    SVC-->>API: unit_with_reporting
    API-->>FE: Unit details

    Note over FE,DB: Get available years
    FE->>API: GET /api/v1/backoffice/years
    API->>SVC: get_available_years()
    SVC->>REPO: query_distinct_years()
    REPO->>DB: SELECT DISTINCT year FROM carbon_reports
    DB-->>REPO: year_list
    REPO-->>SVC: years
    SVC-->>API: sorted_years
    API-->>FE: {"years": [...], "latest": 2025}
```

## 6. Audit Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as audit Router
    participant SVC as AuditService
    participant REPO as AuditRepo
    participant DB as Database

    FE->>API: GET /api/v1/audit/logs
    API->>SVC: get_audit_logs(filters, pagination)
    SVC->>REPO: query_logs(filters, page, page_size)
    REPO->>DB: SELECT * FROM audit_documents WHERE...
    DB-->>REPO: audit_records
    REPO-->>SVC: list[audit_logs]
    SVC-->>API: audit_data
    API-->>FE: Paginated audit logs

    Note over FE,DB: Get audit detail
    FE->>API: GET /api/v1/audit/logs/detail
    API->>SVC: get_audit_detail(log_id)
    SVC->>REPO: get_by_id(log_id)
    REPO->>DB: SELECT * FROM audit_documents WHERE id=?
    DB-->>REPO: audit_record
    REPO-->>SVC: audit_detail
    SVC-->>API: detailed_log
    API-->>FE: Audit log detail
```

## 7. Data Sync Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as data_sync Router
    participant SVC as DataIngestionService
    participant REPO as IngestionRepo
    participant DB as Database
    participant BG as Background Task

    FE->>API: POST /api/v1/sync/data-entries/{module_type_id}
    API->>SVC: validate_and_create_job(payload)
    SVC->>REPO: create_job(payload)
    REPO->>DB: INSERT INTO data_ingestion_jobs...
    DB-->>REPO: job_id
    REPO-->>SVC: job_record
    SVC->>BG: schedule_ingestion(job_id)
    BG-->>SVC: scheduled
    SVC-->>API: job_status
    API-->>FE: {"job_id": 123, "status": "pending"}

    Note over FE,DB: Stream job updates
    FE->>API: GET /api/v1/sync/jobs/{jobId}/stream
    API->>BG: start_streaming(job_id)
    loop Every 2 seconds
        BG->>REPO: get_job_by_id(job_id)
        REPO->>DB: SELECT * FROM data_ingestion_jobs WHERE id=?
        DB-->>REPO: job_record
        REPO-->>BG: job_status
        BG->>FE: SSE event: job_status
    end
```

## 8. Files Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as files Router
    participant SVC as FileService
    participant STORAGE as S3/Local Storage

    FE->>API: GET /api/v1/files/list/{path}
    API->>SVC: list_files(path)
    SVC->>STORAGE: list_directory(path)
    STORAGE-->>SVC: file_list
    SVC-->>API: files
    API-->>FE: File listing

    Note over FE,DB: Upload file
    FE->>API: POST /api/v1/files/temp-upload
    API->>SVC: upload_file(file, path)
    SVC->>STORAGE: save_file(file, path)
    STORAGE-->>SVC: file_path
    SVC-->>API: upload_result
    API-->>FE: {"path": "tmp/123/file.csv"}

    Note over FE,DB: Download file
    FE->>API: GET /api/v1/files/{path}
    API->>SVC: get_file(path)
    SVC->>STORAGE: read_file(path)
    STORAGE-->>SVC: file_content
    SVC-->>API: file_stream
    API-->>FE: File content
```

## 9. Architecture Layer Diagram

```mermaid
graph TB
    subgraph Frontend["Frontend (Vue 3 + Quasar)"]
        FE[Components & Stores]
    end

    subgraph Backend["Backend (FastAPI)"]
        subgraph API["API Layer (Routes)"]
            AUTH[auth.py]
            CR[carbon_report.py]
            CM[carbon_report_module.py]
            BACK[backoffice.py]
            FACT[factors.py]
            AUDIT[audit.py]
            SYNC[data_sync.py]
            FILES[files.py]
        end

        subgraph Services["Service Layer"]
            AUTH_SVC[AuthService]
            CR_SVC[CarbonReportService]
            CM_SVC[ModuleService]
            BACK_SVC[BackofficeService]
            FACT_SVC[FactorService]
            AUDIT_SVC[AuditService]
            SYNC_SVC[DataIngestionService]
            FILES_SVC[FileService]
        end

        subgraph Repositories["Repository Layer"]
            AUTH_REPO[UserRepo]
            CR_REPO[CarbonReportRepo]
            CM_REPO[ModuleRepo]
            BACK_REPO[UnitRepo]
            FACT_REPO[FactorRepo]
            AUDIT_REPO[AuditRepo]
            SYNC_REPO[IngestionRepo]
        end

        subgraph Core["Core Infrastructure"]
            DEPS[Dependencies]
            SECURITY[Security/JWT]
            POLICY[Policy Engine]
            LOGGING[Logging]
            EXCEPTIONS[Exception Handlers]
        end
    end

    subgraph Database["Database (PostgreSQL)"]
        DB[(Tables)]
    end

    FE --> API
    API --> DEPS
    DEPS --> SECURITY
    DEPS --> POLICY
    API --> Services
    Services --> Repositories
    Repositories --> DB
    Services --> CORE
    API --> EXCEPTIONS
    API --> LOGGING

    style Frontend fill:#e1f5ff
    style Backend fill:#f0f4c3
    style Database fill:#fff9c4
    style API fill:#bbdefb
    style Services fill:#c8e6c9
    style Repositories fill:#ffe0b2
    style Core fill:#e1bee7
```

## 10. Request Processing Flow

```mermaid
flowchart TD
    A[HTTP Request] --> B{Authentication?}
    B -->|Yes| C[JWT Token Validation]
    B -->|No| D[Allow Public Endpoint]
    C --> E{Valid Token?}
    E -->|No| F[401 Unauthorized]
    E -->|Yes| G[Extract User Info]
    G --> H{Authorization?}
    H -->|Yes| I[Permission Check]
    H -->|No| J[Allow Public Route]
    I --> K{Has Permission?}
    K -->|No| L[403 Forbidden]
    K -->|Yes| M[Route Handler]
    D --> M
    J --> M
    M --> N[Service Layer]
    N --> O[Repository Layer]
    O --> P[Database Query]
    P --> Q[Process Results]
    Q --> R[Apply Business Logic]
    R --> S[Create Response]
    S --> T[Pydantic Validation]
    T --> U[JSON Serialization]
    U --> V[HTTP Response]
    F --> V
    L --> V

    style A fill:#e3f2fd
    style V fill:#e8f5e9
    style F fill:#ffebee
    style L fill:#ffebee
    style P fill:#fff3e0
    style T fill:#f3e5f5
```

## 11. Module Data Flow (Detailed)

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as Module Router
    participant SVC as ModuleHandlerService
    participant FACTOR_SVC as FactorService
    participant REPO as DataEntryRepo
    participant DB as Database

    Note over FE,DB: Get module items
    FE->>API: GET /api/v1/modules/{unit_id}/{year}/{module_id}/items
    API->>SVC: get_module_items(module_id, filters)
    SVC->>REPO: query_by_module(module_id, filters)
    REPO->>DB: SELECT * FROM data_entries WHERE module_id=?
    DB-->>REPO: item_records
    REPO-->>SVC: list[items]
    SVC->>SVC: enrich_with_factors(items)
    loop For each item
        SVC->>FACTOR_SVC: get_factor(factor_id)
        FACTOR_SVC->>REPO: get_factor_by_id(factor_id)
        REPO->>DB: SELECT * FROM factors WHERE id=?
        DB-->>REPO: factor
        REPO-->>FACTOR_SVC: factor_data
        FACTOR_SVC-->>SVC: factor
        SVC->>SVC: calculate_emissions(item, factor)
    end
    SVC-->>API: items_with_emissions
    API-->>FE: Module items

    Note over FE,DB: Update item
    FE->>API: PATCH /api/v1/modules/{unit_id}/{year}/{module_id}/items/{item_id}
    API->>SVC: update_item(item_id, payload)
    SVC->>SVC: validate_update(payload)
    SVC->>REPO: update(item_id, data)
    REPO->>DB: UPDATE data_entries SET...
    DB-->>REPO: updated
    REPO-->>SVC: updated_item
    SVC->>SVC: recalculate_emissions(item)
    SVC->>FACTOR_SVC: get_primary_factor(item)
    FACTOR_SVC-->>SVC: factor
    SVC->>SVC: compute_new_emissions(item, factor)
    SVC-->>API: updated_item_with_emissions
    API-->>FE: Updated item
```

## 12. Audit Trail Creation Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as Module Router
    participant SVC as ModuleService
    participant AUDIT_SVC as AuditDocumentService
    participant REPO as DataEntryRepo
    participant AUDIT_REPO as AuditRepo
    participant DB as Database

    FE->>API: POST /api/v1/modules/.../items
    API->>SVC: create_item(payload)
    SVC->>REPO: insert(item)
    REPO->>DB: INSERT INTO data_entries...
    DB-->>REPO: new_id
    REPO-->>SVC: created_item

    Note over SVC,AUDIT_REPO: Create audit trail
    SVC->>AUDIT_SVC: create_audit_log(change_type, entity, user)
    AUDIT_SVC->>AUDIT_SVC: compute_data_diff(old, new)
    AUDIT_SVC->>AUDIT_SVC: compute_data_snapshot(new)
    AUDIT_SVC->>AUDIT_REPO: insert_audit_log(audit_doc)
    AUDIT_REPO->>DB: INSERT INTO audit_documents...
    DB-->>AUDIT_REPO: audit_id
    AUDIT_REPO-->>AUDIT_SVC: created
    AUDIT_SVC-->>SVC: audit_created
    SVC-->>API: item_with_audit
    API-->>FE: Created item
```

## Notes

### Legend

- **FE**: Frontend (Vue 3 + Quasar)
- **API**: FastAPI Route Handler
- **SVC**: Service Layer (Business Logic)
- **REPO**: Repository Layer (Data Access)
- **DB**: PostgreSQL Database
- **BG**: Background Task Processor
- **STORAGE**: S3 or Local File Storage

### Key Patterns

1. **Three-Layer Architecture**: Routes → Services → Repositories
2. **Dependency Injection**: All dependencies injected via FastAPI Depends
3. **Async/Await**: All database operations are asynchronous
4. **Audit Trail**: All mutations create audit documents
5. **Permission-Based Authorization**: Checked before route handler execution
6. **Pydantic Validation**: Request/response validation at API boundary

### Frontend API Client

- **Library**: `ky` (HTTP client)
- **Base URL**: `/api/v1/`
- **Authentication**: JWT tokens in cookies
- **Error Handling**: Automatic refresh on 401, redirect on session expiry
