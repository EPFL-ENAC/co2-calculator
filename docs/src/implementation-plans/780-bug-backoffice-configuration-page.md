# Refactoring: Data Management Upload Components

## Problem

The `ModuleConfig.vue` and `SubmoduleConfig.vue` components had significant code duplication:

- **~200 lines** of duplicated upload card UI logic in each file
- **Duplicated helper functions**: `cardStyle`, `dataButtonColor`, `factorButtonColor`, `dataButtonLabel`, `factorButtonLabel`, `downloadLastCsv`, `safeFileName`
- Three similar upload patterns (Data, Factors, References) with nearly identical structure

## Solution

Extracted common patterns into reusable components following Vue's molecule/organism hierarchy.

### New Components Created

#### 1. Composable: `useUploadCard.ts`

**Location**: `frontend/src/composables/useUploadCard.ts`

Extracts all duplicated helper functions:

- Button color logic (`dataButtonColor`, `factorButtonColor`, `getButtonColor`)
- Button labels (`dataButtonLabel`, `factorButtonLabel`, `getButtonLabel`)
- File handling (`safeFileName`, `downloadLastCsv`)
- Card styling (`cardStyle`)
- Job info display (`getJobInfo`)
- Error handling (`hasErrorOrWarning`, `getErrorDetails`)

#### 2. Base Component: `UploadCard.vue`

**Location**: `frontend/src/components/molecules/data-management/UploadCard.vue`

Generic card component that handles:

- Card styling with dynamic border/background based on state
- Title and description with optional subtext
- Upload button with loading state
- Recalculation button with warning indicator (optional)
- Computed factor button (optional)
- Download last CSV button (when job exists)
- File metadata display (filename, rows processed, timestamp)
- Error/warning banner with stats
- Mandatory indicator (\*)

**Props**:

```typescript
interface Props {
  title: string;
  description: string;
  showMandatoryIndicator?: boolean;
  descriptionSubtext?: string;
  buttonColor: string;
  buttonLabel: string;
  buttonIcon?: string;
  isDisabled?: boolean;
  isLoading?: boolean;
  lastJob?: SyncJobResponse;
  targetType?: TargetType;
  hasRecalcButton?: boolean;
  recalcStatus?: RecalculationStatus;
  recalcRunning?: boolean;
  hasComputedFactorButton?: boolean;
  computedFactorRunning?: boolean;
  isComputedFactorDisabled?: boolean;
}
```

#### 3. Specialized Components

**UploadCardData.vue** - Data entries card

- Wraps UploadCard with data-specific logic
- Shows recalculation button only if factors exist
- Uses `TargetType.DATA_ENTRIES`

**UploadCardFactors.vue** - Factors card

- Wraps UploadCard with factor-specific logic
- Special description for headcount module
- Computed factor button for Research Facilities
- Full error/stats display

**UploadCardReferences.vue** - References card

- Fully functional implementation with `/sync/dispatch`
- Uses `TargetType.REFERENCE_DATA` and `EntityType.MODULE_UNIT_SPECIFIC`
- Independent job handling (not dependent on parent)
- Same error/download/stats features as other cards

### Refactored Files

#### ModuleConfig.vue

**Changes**:

- Imported new components (`UploadCardData`, `UploadCardFactors`)
- Replaced ~200 lines of duplicated card UI with component usage
- Removed duplicated helper functions (moved to composable)
- Kept `downloadLastCsv` as it's still used by components

**Before**:

```vue
<div class="row q-pb-md" style="gap: 1rem">
  <q-card v-if="getImportRow(common).hasData" ...>
    <!-- 70 lines of data card -->
  </q-card>
  <q-card v-if="getImportRow(common).hasFactors" ...>
    <!-- 130 lines of factors card -->
  </q-card>
</div>
```

**After**:

```vue
<div class="row q-pb-md" style="gap: 1rem">
  <UploadCardData
    v-if="getImportRow(common).hasData"
    :row="getImportRow(common)"
    @upload="openDataEntryDialog($event, TargetType.DATA_ENTRIES)"
    @download="downloadLastCsv"
    @recalculate="triggerTypeRecalculation"
  />
  
  <UploadCardFactors
    v-if="getImportRow(common).hasFactors"
    :row="getImportRow(common)"
    @upload="openDataEntryDialog($event, TargetType.FACTORS)"
    @download="downloadLastCsv"
    @recalculate="triggerTypeRecalculation"
  />
</div>
```

#### SubmoduleConfig.vue

**Changes**:

- Imported new components (`UploadCardData`, `UploadCardFactors`, `UploadCardReferences`)
- Replaced ~200 lines of duplicated card UI with component usage
- Removed duplicated helper functions
- Added References card with full functionality
- Passed `anyComputedFactorRunning` prop for computed factor button disabling

### i18n Translations

Added missing translation:

```typescript
data_management_reupload_reference: {
  en: 'ReUpload Reference',
  fr: 'Re-téléverser référence',
}
```

Existing translations used:

- `data_management_references`
- `data_management_references_description`
- `data_management_upload_reference`
- `data_management_other_*` (train stations, airports, rooms)

## Benefits

### Code Quality

- **DRY**: Eliminated ~400 lines of duplicated code
- **Maintainability**: Single source of truth for upload card logic
- **Testability**: Individual components can be tested in isolation
- **Readability**: Clear separation of concerns

### Feature Parity

All three card types now have consistent features:

- ✅ Upload button with proper labeling
- ✅ Download last CSV button (when job exists)
- ✅ File metadata display (filename, rows processed, timestamp)
- ✅ Error/warning display with full details
- ✅ Stats display (rows_processed, rows_skipped, etc.)
- ✅ Loading states (spinner during upload)
- ✅ Disabled states (when module/submodule is disabled)
- ✅ Mandatory indicator (\*)
- ✅ Recalculation button (Data & Factors)
- ✅ Computed factor button (Factors - Research Facilities)

### New Functionality

- **References card**: Fully functional upload with `/sync/dispatch` endpoint
- Supports `TargetType.REFERENCE_DATA` (3)
- Uses `EntityType.MODULE_UNIT_SPECIFIC` (3) in config
- Same job tracking and error handling as other upload types

## Implementation Details

### References Card Implementation

The References card implements the actual sync dispatch:

```typescript
const syncPayload = {
  module_type_id: props.row.moduleTypeId,
  year: props.year,
  provider_type: "csv",
  target_type: TargetType.REFERENCE_DATA,
  data_entry_type_id: props.row.dataEntryTypeId,
  config: {
    entity_type: EntityType.MODULE_UNIT_SPECIFIC,
  },
};

const jobId = await backofficeDataManagement.initiateSync(syncPayload);
```

Backend endpoint `/sync/dispatch` already exists and accepts `entity_type` in config.

### Computed Factor Button

For Research Facilities module:

- Button shown only when `module === 'research_facilities'`
- Disabled when any computed factor sync is running (`anyComputedFactorRunning`)
- Triggers confirmation dialog before starting

## Files Changed

### New Files

- `frontend/src/composables/useUploadCard.ts`
- `frontend/src/components/molecules/data-management/UploadCard.vue`
- `frontend/src/components/molecules/data-management/UploadCardData.vue`
- `frontend/src/components/molecules/data-management/UploadCardFactors.vue`
- `frontend/src/components/molecules/data-management/UploadCardReferences.vue`

### Modified Files

- `frontend/src/components/organisms/data-management/ModuleConfig.vue`
- `frontend/src/components/organisms/data-management/SubmoduleConfig.vue`
- `frontend/src/i18n/backoffice_data_management.ts`

## Testing Checklist

- [ ] Data upload works for all module types
- [ ] Factor upload works for all module types
- [ ] Reference upload works (when backend supports it)
- [ ] Download last CSV works for data, factors, and references
- [ ] Error/warning display shows correctly
- [ ] Recalculation button appears only when factors exist
- [ ] Computed factor button appears only for Research Facilities
- [ ] Disabled states work correctly
- [ ] Loading states show during upload
- [ ] File metadata displays correctly (filename, rows, timestamp)
- [ ] All i18n translations work (EN/FR)

## Future Improvements

1. **Extract error display**: Could be a separate component if reused elsewhere
2. **Add unit tests**: For composable functions and component logic
3. **Visual regression tests**: Ensure UI consistency across card types
4. **Accessibility**: Add ARIA labels and keyboard navigation
5. **Performance**: Consider memoization for expensive calculations
