---
status: delivered
last_updated: 2026-05-05
summary: Component hierarchy, composables, and Pinia stores backing Data Management.
---

# Architecture

## Component Hierarchy

```mermaid
graph TD
    DMP[DataManagementPage.vue<br/>233 lines] --> NH[NavigationHeader<br/>organisms/backoffice]
    DMP --> YS[Year Selection Card]
    DMP --> MC[ModuleConfig × N<br/>organisms]
    DMP --> ROS[ReductionObjectivesSection<br/>organisms<br/>463 lines]

    YS --> YS1[Year Selector Dropdown]
    YS --> YS2[Sync Units Button]
    YS --> YC[Create Year Card<br/>when no config]

    MC --> MCS[ModuleConfigSection<br/>molecules]
    MC --> MUS[ModuleUploadsSection<br/>molecules]
    MC --> MRD[ModuleRecalculationDialog<br/>molecules]
    MC --> SC[SubmoduleConfig<br/>organisms<br/>43 lines]
    MC --> DED[DataEntryDialog<br/>organisms<br/>36 lines]

    MUS --> UC[UploadCard × 3<br/>molecules]
    MUS --> SI[SubmoduleItem<br/>molecules]

    UC --> UC1[UploadCardData]
    UC --> UC2[UploadCardFactors]
    UC --> UC3[UploadCardReferences]

    DED --> DEDC[DataEntryDialogContent<br/>molecules<br/>270 lines]

    ROS --> DED2[DataEntryDialog<br/>for reduction objectives]
```

## Component Summary

| Type     | Component                        | Lines | Responsibility                                                    |
| -------- | -------------------------------- | ----- | ----------------------------------------------------------------- |
| Organism | `DataManagementPage.vue`         | 233   | Page root: year selection, module iteration, dialog orchestration |
| Organism | `ModuleConfig.vue`               | 198   | Single module: expansion item with config, uploads, submodules    |
| Organism | `SubmoduleConfig.vue`            | 43    | Renders submodule list within a module                            |
| Organism | `DataEntryDialog.vue`            | 36    | Thin wrapper around DataEntryDialogContent                        |
| Organism | `ReductionObjectivesSection.vue` | 463   | Reduction objectives: file uploads + 3 goal slots                 |
| Molecule | `ModuleConfigSection.vue`        | 101   | Module enable/disable, uncertainty tagging                        |
| Molecule | `ModuleUploadsSection.vue`       | 121   | Upload cards + recalculation triggers                             |
| Molecule | `DataEntryDialogContent.vue`     | 270   | CSV upload, API connection, copy logic                            |
| Molecule | `SubmoduleItem.vue`              | 250   | Individual submodule row with status                              |
| Molecule | `ModuleRecalculationDialog.vue`  | 86    | Module-wide recalculation confirmation                            |
| Molecule | `ComputedFactorDialog.vue`       | 57    | Computed factor regeneration dialog                               |
| Molecule | `UploadCard.vue`                 | 278   | Base upload card with download, cancel, status                    |
| Molecule | `UploadCardData.vue`             | 66    | Data upload (CSV / API / copy)                                    |
| Molecule | `UploadCardFactors.vue`          | 89    | Factor upload (CSV / computed)                                    |
| Molecule | `UploadCardReferences.vue`       | 408   | Self-contained reference data upload with SSE + cancel            |

## Composables

```mermaid
graph LR
    subgraph Composables
        UDED[useDataEntryDialog.ts<br/>347 lines]
        UMC[useModuleConfig.ts<br/>177 lines]
        UREC[useRecalculation.ts<br/>200 lines]
        USC[useSubmoduleConfig.ts<br/>253 lines]
    end

    UDED --> FS[Files Store]
    UDED --> BDM[BackofficeDataManagement Store]
    UMC --> YCS[YearConfig Store]
    UREC --> BDM
    USC --> YCS
```

| Composable              | Lines | Responsibility                                                     |
| ----------------------- | ----- | ------------------------------------------------------------------ |
| `useDataEntryDialog.ts` | 347   | CSV upload, API connection, previous year copy, SSE job monitoring |
| `useModuleConfig.ts`    | 177   | Module enable/disable, uncertainty management, job status lookup   |
| `useRecalculation.ts`   | 200   | Recalculation status tracking, trigger module/type recalculation   |
| `useSubmoduleConfig.ts` | 253   | Submodule enable/disable, threshold configuration                  |

## Stores

### `useBackofficeDataManagement`

```mermaid
classDiagram
    class useBackofficeDataManagement {
        +loading: boolean
        +error: string|null
        +syncJobs: Record~year, DataIngestionJob[]~
        +currentYear: number|null
        +sseConnection: EventSource|null
        +fetchSyncJobsByYear(year)
        +fetchLatestSyncJobsByYear(year)
        +initiateSync(params)
        +initiateComputedFactorSync(moduleTypeId, dataEntryTypeId, year)
        +initiateEmissionRecalculation(moduleTypeId, dataEntryTypeId, year)
        +initiateModuleEmissionRecalculation(moduleTypeId, year, onlyStale)
        +subscribeToJobUpdates(jobId, callbacks)
        +cancelJob(jobId, year)
        +syncUnitsFromAccred(targetYear)
        +getPreviousYearSuccessfulJobs(year, moduleTypeId, targetType)
        +getSyncStatusByModule(moduleType, year): number
        +getSyncResultByModule(moduleType, year): number
        +getSuccessRate(job): number
        +isJobFinished(moduleType, year): boolean
        +hasJobSucceeded(moduleType, year): boolean
    }
```

### `useYearConfigStore`

```mermaid
classDiagram
    class useYearConfigStore {
        +config: YearConfigurationResponse|null
        +loading: boolean
        +notFound: boolean
        +fetchConfig(year)
        +createConfig(year, payload)
        +updateConfig(year, payload)
        +unifiedModuleConfig: Record~string, UnifiedModuleConfig~
        +visibleModules: Module[]
        +anyModuleIncomplete: boolean
        +getModule(moduleName): UnifiedModuleConfig|null
        +getSubmodule(moduleName, subKey): UnifiedSubmoduleConfig|null
        +isModuleVisible(module): boolean
        +isSubmoduleVisible(module, subKey): boolean
        +isModuleIncomplete(module): boolean
        +isSubmoduleIncomplete(sub): boolean
    }
```

## File Structure

```
frontend/src/
├── pages/back-office/
│   └── DataManagementPage.vue          # Page root (233 lines)
├── components/
│   ├── organisms/data-management/
│   │   ├── ModuleConfig.vue
│   │   ├── SubmoduleConfig.vue
│   │   ├── DataEntryDialog.vue
│   │   └── ReductionObjectivesSection.vue
│   └── molecules/data-management/
│       ├── ModuleConfigSection.vue
│       ├── ModuleUploadsSection.vue
│       ├── DataEntryDialogContent.vue
│       ├── SubmoduleItem.vue
│       ├── ModuleRecalculationDialog.vue
│       ├── ComputedFactorDialog.vue
│       ├── UploadCard.vue
│       ├── UploadCardData.vue
│       ├── UploadCardFactors.vue
│       └── UploadCardReferences.vue
├── composables/
│   ├── useDataEntryDialog.ts
│   ├── useModuleConfig.ts
│   ├── useRecalculation.ts
│   └── useSubmoduleConfig.ts
├── stores/
│   ├── backofficeDataManagement.ts
│   └── yearConfig.ts
├── constant/
│   ├── backoffice-module-config.ts
│   └── modules.ts
└── api/http.ts
```
