---
status: delivered
last_updated: 2026-05-05
summary: Year configuration lifecycle, data upload flow, recalculation flow, and SSE job monitoring.
---

# Data Flows

## 1. Year Configuration Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant P as Page
    participant S as YearConfigStore
    participant API as Backend API

    U->>P: Select year from dropdown
    P->>S: watch(selectedYear) triggers
    S->>API: GET /year-configuration/{year}

    alt Config exists (200)
        API-->>S: YearConfigurationResponse
        S->>P: config updated
        P->>P: Render ModuleConfig × N
        P->>P: Render ReductionObjectivesSection
    else No config (404)
        API-->>S: 404 Not Found
        S->>P: notFound = true
        P->>P: Show "Create Year" card
        U->>P: Click "Create Year"
        P->>API: POST /year-configuration/{year}
        API-->>P: Created
    end

    S->>P: watch(loading) updates
    P->>P: Show/Hide Quasar Loading overlay
```

## 2. Data Upload Flow

```mermaid
flowchart TD
    Start[User clicks Upload/Connect] --> OpenDialog[openDataEntryDialog<br/>ImportRow + TargetType]
    OpenDialog --> Dialog[DataEntryDialogContent opens]

    Dialog --> Choice{Choose method}

    Choice -->|CSV| CSV[Select files]
    CSV --> Upload[filesStore.uploadTempFiles<br/>POST /files/temp]
    Upload --> InitCSV[initiateSync provider: csv<br/>POST /sync/dispatch]

    Choice -->|API| API[Fill credentials]
    API --> InitAPI[initiateSync provider: api<br/>POST /sync/dispatch]

    Choice -->|Copy| Copy[loadPreviousYearJobs<br/>GET /sync/jobs/year/{y-1}/latest]
    Copy --> SelectJob[Select job from list]
    SelectJob --> InitCopy[initiateSync provider: copy<br/>POST /sync/dispatch]

    InitCSV --> GetJobId[Returns job_id]
    InitAPI --> GetJobId
    InitCopy --> GetJobId

    GetJobId --> Subscribe[subscribeToJobUpdates<br/>SSE: GET /sync/jobs/{jobId}/stream]

    Subscribe --> Monitor{Monitor progress}
    Monitor -->|Update| Update[Update syncJobs store]
    Update --> Monitor
    Monitor -->|Complete| Complete[On completion handler]

    Complete --> Refresh1[refreshRecalculationStatus]
    Complete --> Refresh2[fetch year config]
    Complete --> Notify[Show notification]

    Notify --> End[Dialog closes]
```

## 3. Recalculation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant MC as ModuleConfig
    participant MRD as ModuleRecalculationDialog
    participant BDM as BackofficeDataManagement
    participant API as Backend
    participant SSE as SSE Stream

    Note over MC: Factors updated →<br/>needs_recalculation = true
    MC->>U: Show "Recalculation needed" badge

    U->>MC: Click "Recalculate Emissions"
    MC->>MRD: openRecalcDialog(moduleTypeId)
    MRD->>U: Show stale types list

    U->>MRD: Confirm recalculation
    MRD->>BDM: confirmModuleRecalculation(moduleTypeId)
    BDM->>API: POST /sync/recalculate-emissions/{moduleId}?only_stale=true
    API-->>BDM: Returns job_id

    BDM->>SSE: GET /sync/jobs/{jobId}/stream
    SSE-->>BDM: Progress updates

    alt Success
        SSE-->>BDM: result = SUCCESS
        BDM->>U: Show success notification
    else Warning
        SSE-->>BDM: result = WARNING
        BDM->>U: Show warning notification
    else Error
        SSE-->>BDM: result = ERROR
        BDM->>U: Show error notification
    end

    BDM->>API: GET /sync/recalculation-status
    API-->>BDM: Clear needs_recalculation flag
    BDM->>MC: refreshRecalculationStatus
    MC->>MC: Hide badge
```

## SSE Job Monitoring

```mermaid
stateDiagram-v2
    [*] --> Disconnected
    Disconnected --> Connecting: subscribeToJobUpdates(jobId)
    Connecting --> Connected: SSE opened
    Connected --> Updating: onmessage
    Updating --> Updating: state update
    Updating --> Updating: progress update
    Updating --> Finished: state = FINISHED
    Finished --> Disconnected: unsubscribe
    Disconnected --> [*]

    Connecting --> Error: onerror
    Error --> Disconnected: close
```

## Job Status Flow

```mermaid
stateDiagram-v2
    [*] --> NOT_STARTED
    NOT_STARTED --> QUEUED: initiateSync
    QUEUED --> RUNNING: scheduler picks up
    RUNNING --> FINISHED: processing complete

    FINISHED --> [*]: result = SUCCESS
    FINISHED --> [*]: result = WARNING
    FINISHED --> [*]: result = ERROR

    RUNNING --> CANCELLED: cancelJob
    QUEUED --> CANCELLED: cancelJob
    CANCELLED --> [*]: result = ERROR, cancelled = true
```
