# PRD: Year Configuration & Data Management

## 🎯 Objective

Centralize annual administrative settings, emission thresholds, uncertainty levels, and institutional reduction goals into a single source of truth via the `year_configuration` table. This data drives UI logic (red highlighting for thresholds) and institutional projection calculations.

---

## 🗄️ 1. Data Architecture

### Database Table: `year_configuration`

| Column              | Type       | Constraints                 | Description                                        |
| :------------------ | :--------- | :-------------------------- | :------------------------------------------------- |
| `year`              | `INTEGER`  | `PRIMARY KEY`               | The reference year (e.g., 2025).                   |
| `is_started`        | `BOOLEAN`  | `DEFAULT FALSE`             | If `true`, data entry is open for users.           |
| `is_reports_synced` | `BOOLEAN`  | `DEFAULT FALSE`             | If `true`, `carbon_reports` have been initialized. |
| `config`            | `JSONB`    | `NOT NULL`                  | Deep configuration (thresholds, tags, goals).      |
| `updated_at`        | `DATETIME` | `DEFAULT CURRENT_TIMESTAMP` | Last modification timestamp.                       |

### JSON Schema (`config` column)

The JSON structure is keyed by `ModuleTypeEnum` and `DataEntryTypeEnum` as strings to ensure $O(1)$ lookup in the calculation engine.

```typescript
interface YearConfigJSON {
  modules: {
    [module_type_id: string]: {
      enabled: boolean;
      uncertainty_tag: "low" | "medium" | "high" | "none";
      submodules: {
        [data_entry_type_id: string]: {
          enabled: boolean;
          threshold: number | null; // Fixed threshold in kgCO2eq
        };
      };
    };
  };
  reduction_objectives: {
    files: {
      institutional_footprint: FileMetadata | null;
      population_projections: FileMetadata | null;
      unit_scenarios: FileMetadata | null;
    };
    goals: Array<{
      target_year: number;
      reduction_percentage: number; // Decimal (e.g., 0.4 for 40%)
      reference_year: number;
    }>;
  };
}

interface FileMetadata {
  path: string;
  filename: string;
  uploaded_at: string; // ISO format
}
```

---

## 🛣️ 2. API Specifications

### `GET /api/v1/year-configuration/{year}`

- **Action**: Fetch configuration.
- **Logic**: If no record exists, the backend must return a default object generated from `ModuleTypeEnum` and `MODULE_TYPE_TO_DATA_ENTRY_TYPES`.

### `PATCH /api/v1/year-configuration/{year}`

- **Action**: Partial update of flags or the `config` object.
- **Validation**:
  - `reduction_percentage` must be between `0` and `1`.
  - `target_year` must be `> year`.
- **Audit**: Trigger an entry in `audit_documents` with `entity_type="year_configuration"`.

### `POST /api/v1/year-configuration/{year}/upload`

- **Payload**: `multipart/form-data` (`file`, `category`).
- **Categories**: `footprint`, `population`, `scenarios`.
- **Logic**: Store file in defined storage path; update `config.reduction_objectives.files` with metadata.

---

## 🎨 3. Frontend Requirements (Vue 3 / Quasar)

### State Management

- **Store**: Pinia `useYearConfigStore`.
- **Methods**: `fetchConfig(year)`, `updateConfig(year, patch)`, `uploadFile(year, category, file)`.

### Components

1. **Year Context**: A dropdown to switch the configuration year globally.
2. **Module Activation (Expansion Items)**:
   - **Toggle**: Enable/Disable entire module.
   - **Uncertainty**: Radio group for High/Medium/Low.
   - **Submodule Table**: List of `data_entry_types` with individual toggles and numeric inputs for **Fixed Threshold**.
3. **Reduction Objectives Form**:
   - Three sets of inputs for goals (Target Year, %, Ref Year).
   - `QFile` uploaders with status indicators (Success/Error/Existing).

### UI Logic

- **Visual Warning**: Any emission value $V$ in the app is displayed in **red** if:
  $$V > \text{config.modules[mod].submodules[submod].threshold}$$

---

## ✅ 4. Acceptance Criteria

- [x] **Database**: Alembic migration adds `year_configuration` with `JSONB`.
- [x] **Backend**: Pydantic validation ensures JSON integrity against Enums.
- [x] **Audit**: All changes logged in `audit_documents` with `data_diff`.
- [ ] **UI**: "Configuration" page matches provided design (Frame 235.jpg).
- [ ] **Reactive**: Threshold changes immediately reflect in data entry tables without page refresh.
- [ ] **Files**: CSV uploads correctly map to the storage path in the JSON metadata.
- [ ] **Frontend Type Safety**: All TypeScript errors resolved.

---

## 📝 Implementation Notes

### Backend Implementation (Completed)

1. **Model**: `app/models/year_configuration.py`
   - SQLModel with proper JSONB column configuration
   - Uses `col()` for SQLAlchemy comparisons (Mypy strict compliance)

2. **Migration**: `alembic/versions/2026_03_31_0000-a1b2c3d4e5f7_add_year_configuration.py`
   - Creates table with proper indexes
   - Successfully applied to database

3. **Schemas**: `app/schemas/year_configuration.py`
   - Complete type definitions with Pydantic validation
   - Validation rules for percentage (0-1) and year constraints

4. **Service**: `app/services/year_config_service.py`
   - Default config generator using `ModuleTypeEnum` mappings
   - Helper functions for threshold checking

5. **API**: `app/api/v1/year_configuration.py`
   - All endpoints implemented with proper validation
   - Audit logging integrated
   - File upload handling with category mapping

### Frontend Implementation (In Progress)

1. **Store**: `frontend/src/stores/yearConfig.ts`
   - Pinia store with all required methods
   - Type-safe configuration management

2. **Components**:
   - `ModuleConfigItem.vue` - Module-level expansion items
   - `ReductionObjectives.vue` - File uploads and goals
   - `ModulesConfigNew.vue` - Main configuration page

3. **Known Issues**:
   - TypeScript type errors in component props and table slots
   - Needs i18n translations for new UI elements
   - Threshold visual warning logic not yet implemented

### Technical Decisions

1. **File Storage Paths**: Used subdirectories under `reduction_objectives/` as specified
2. **is_started Logic**: Kept as written in PRD (true = OPEN)
3. **Auto-creation**: Lazy creation on first API access (manual only per PRD)
4. **Threshold UI**: Deferred to future iteration (composable/hook approach)

### Files Changed

- **Backend**: 7 files (models, schemas, API, service, migration, router)
- **Frontend**: 5 files (store, 3 components, 1 page)
- **Docs**: 1 file (ERD updated automatically)

**Total**: 13 files, ~1745 insertions

---

## 🔄 Next Steps

1. **Fix Frontend Type Errors**:
   - Resolve TypeScript errors in `ModuleConfigItem.vue`
   - Fix `ModulesConfigNew.vue` type mismatches
   - Address `ReductionObjectives.vue` type issues

2. **Add Tests**:
   - Backend API endpoint tests
   - Frontend component tests
   - Integration tests for file uploads

3. **Implement Remaining Features**:
   - Threshold visual warning (red highlighting)
   - i18n translations
   - Year selector component

4. **Documentation**:
   - API documentation updates
   - User guide for configuration management

---

**Status**: Backend complete ✅ | Frontend UI complete (type errors pending) ⚠️ | Tests pending 📋
