# Professional Travel Module - Implementation Summary

**Issue**: #18 - Professional Travel Module

**Logical Implementation Flow**:

1. Backend Foundation (Ch 1-2): Database + CRUD operations
2. Frontend Foundation (Ch 3-4): Module config + UI basics
3. Data Display (Ch 5-6): Table + Total/Results
4. Data Entry (Ch 7-8): Form + CO2 calculations
5. Integration (Ch 9): CSV/API import

---

## Chapter 1: Database Model & Migration

### Goal

Create database schema with audit fields and proper indexes for the professional travel module.

### Database Schema

```sql
CREATE TABLE professional_travels (
    -- Primary key
    id SERIAL PRIMARY KEY,

    -- Traveler information
    traveler_id VARCHAR(50) NOT NULL,        -- Links to headcount.cf_user_id
    traveler_name VARCHAR(255) NOT NULL,     -- Display name from headcount (dropdown from Headcount module)

    -- Trip details
    origin VARCHAR(255) NOT NULL,            -- City name (airport city for plane, train station city for train)
    destination VARCHAR(255) NOT NULL,       -- City name (airport city for plane, train station city for train)
    departure_date DATE,                     -- Start date (OPTIONAL - approximate date of travel)
    return_date DATE,                        -- End date (shown when is_round_trip is true)
    is_round_trip BOOLEAN DEFAULT FALSE,     -- If true, duplicates as 2 rows (Departure>Destination and Destination>Departure)

    -- Transport information
    transport_mode VARCHAR(50) NOT NULL,     -- 'flight' | 'train' (Type: Plane or Train)
    class VARCHAR(50),                       -- Train: 'class_1' | 'class_2'
                                            -- Plane: 'first' | 'business' | 'eco' | 'eco_plus'
    distance_km FLOAT,                       -- Distance in km (auto-calculated or preprocessed from given data)
    number_of_trips INTEGER DEFAULT 1,       -- Number of trips (default: 1)

    -- Emissions calculation
    kg_co2eq FLOAT,                          -- CO2 emissions in kg (auto-calculated or preprocessed from given data)

    -- Organization & filtering
    unit_id VARCHAR(50) NOT NULL,            -- Cost center/unit
    year INTEGER NOT NULL,                   -- Calculated from departure_date for filtering (or current year if null)

    -- Data source tracking
    provider VARCHAR(50),                    -- 'api' | 'csv' | 'manual' (where data came from)

    -- Audit trail (from AuditMixin)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),                  -- User who created record
    updated_by VARCHAR(50),                  -- User who last updated record

    -- Performance indexes
    INDEX idx_unit_year (unit_id, year),     -- Primary filtering
    INDEX idx_traveler (traveler_id),        -- Filter by person
    INDEX idx_created_by (created_by)        -- Permission filtering for std users
);
```

### Model Structure

**File**: `backend/app/models/professional_travel.py` (NEW)

Following HeadCount pattern with these DTOs:

1. **`AuditMixin`**: Reusable mixin providing created_at, updated_at, created_by, updated_by
2. **`ProfessionalTravelBase`**: Shared fields (all trip data except id/provider/audit)
3. **`ProfessionalTravel`**: Table model (inherits Base + AuditMixin + adds id/provider/year)
4. **`ProfessionalTravelCreate`**: POST request DTO (Base fields, all required)
5. **`ProfessionalTravelUpdate`**: PATCH request DTO (all fields optional)
6. **`ProfessionalTravelItemResponse`**: GET response DTO (Base + id + provider + can_edit flag)
7. **`ProfessionalTravelList`**: Paginated response with items, total, page, page_size

### Key Field Decisions

**`traveler_id` vs `traveler_name`**:

- `traveler_id`: Links to `headcount.cf_user_id` for validation
- `traveler_name`: Denormalized for display (avoids joins)
- Validation ensures traveler exists in headcount before creation

**`year` field**:

- Calculated from `departure_date.year` automatically
- Used for filtering trips by reporting year
- Updated if departure_date changes

**`provider` field**:

- Tracks data origin for permission decisions
- 'api': From external system (read-only for all)
- 'csv': Bulk import (editable by principals)
- 'manual': User-entered (editable by creator/principals)

**`is_round_trip` handling**:

- If checked, backend creates 2 records:
  - Record 1: origin → destination, departure_date
  - Record 2: destination → origin, return_date
- Each record has full CO2 calculation
- Simplifies querying and aggregation

### Migration

**File**: `backend/alembic/versions/XXXX_create_professional_travels.py` (NEW)

Run: `alembic revision --autogenerate -m "create professional_travels table"`

**Files Summary**:

- **New**: 1 file (model) + 1 migration file

---

## Chapter 2: Repository & Service Layer

### Goal

Implement data access layer with user filtering and business logic with permission checks.

### Repository Layer

**File**: `backend/app/repositories/professional_travel_repo.py` (NEW)

Following `HeadCountRepository` pattern with these methods:

**1. `get_travels(unit_id, year, user, limit, offset, sort_by, sort_order, filter)`**:

- Base query: `SELECT * FROM professional_travels WHERE unit_id = ? AND year = ?`
- User filter for std users: `AND created_by = user.id`
- Text search: `WHERE traveler_name ILIKE '%filter%' OR origin ILIKE '%filter%' OR destination ILIKE '%filter%'`
- Sorting: `ORDER BY {sort_by} {sort_order}` (any column)
- Pagination: `LIMIT {limit} OFFSET {offset}`
- Return: `(List[ProfessionalTravel], total_count)`

**2. `get_by_id(travel_id, user)`**:

- Fetch single record
- Apply same user filtering (std users only see own)
- Return: `Optional[ProfessionalTravel]`
- Used before update/delete operations

**3. `create_travel(data, provider_source, user_id)`**:

- Calculate `year = data.departure_date.year`
- Set `provider = provider_source` ('manual' for user-created)
- Set `created_by = user_id`
- Handle round trip: If `is_round_trip`, create 2 records
- Return: `ProfessionalTravel` (or List if round trip)

**4. `update_travel(travel_id, data, user_id)`**:

- Update only fields provided in data (partial update)
- Recalculate `year` if `departure_date` changed
- Set `updated_by = user_id`, `updated_at = now()`
- Return: `Optional[ProfessionalTravel]`

**5. `delete_travel(travel_id)`**:

- Hard delete from database
- Return: `bool` (success/failure)

**6. `get_summary_stats(unit_id, year, user)`**:

- Aggregate query: `SELECT SUM(kg_co2eq), COUNT(*) ...`
- Apply user filtering for std users
- Return: `{ total_items: int, total_kg_co2eq: float, total_distance_km: float }`

### Service Layer

**File**: `backend/app/services/professional_travel_service.py` (NEW)

Following `HeadcountService` pattern with these components:

**Permission Logic**:

```python
def can_user_edit_item(travel: ProfessionalTravel, user: User) -> bool:
    # API trips are read-only for everyone
    if travel.provider == 'api':
        return False

    # Principals and secondaries can edit manual/CSV trips
    if user.has_role("co2.user.principal") or user.has_role("co2.user.secondary"):
        return True

    # Std users can only edit their own manual trips
    if user.has_role("co2.user.std") and travel.created_by == user.id:
        return True

    return False
```

**CRUD Methods**:

1. **`get_module_data(unit_id, year, user, preview_limit)`**:
   - Call `repo.get_summary_stats()` for totals
   - Call `repo.get_travels()` for preview items (limited)
   - Build `ModuleResponse` with totals + items
   - Add `can_edit` flag to each item via `_to_item_response()`

2. **`get_submodule_data(unit_id, year, user, page, limit, sort_by, sort_order, filter)`**:
   - Call `repo.get_travels()` with full pagination
   - Build `SubmoduleResponse` with items + pagination metadata
   - Add `can_edit` flag to each item

3. **`create_travel(data, provider_source, user)`**:
   - Validate: Traveler exists in headcount (call `_validate_traveler()`)
   - Calculate: Distance and CO2 emissions (call calculation methods from Chapter 8)
   - Call `repo.create_travel()` with calculated values
   - Return response with `can_edit=True` (user just created it)

4. **`update_travel(travel_id, data, user)`**:
   - Fetch record via `repo.get_by_id()` (with user filtering)
   - Check permission: `can_user_edit_item()` → raise 403 if False
   - Validate: If traveler changed, ensure new traveler exists
   - Recalculate: Distance and CO2 if origin/destination/mode/class changed
   - Call `repo.update_travel()` with new values
   - Return response with recalculated `can_edit` flag

5. **`delete_travel(travel_id, user)`**:
   - Fetch record via `repo.get_by_id()` (with user filtering)
   - Check permission: `can_user_edit_item()` → raise 403 if False
   - Call `repo.delete_travel()`
   - Return True on success

**Helper Methods**:

- `_to_item_response(travel, user)`: Convert DB model to DTO + add `can_edit` flag
- `_validate_traveler(traveler_id, unit_id)`: Query HeadCount, raise 422 if not found

### API Endpoints

**File**: `backend/app/api/v1/modules.py` (MODIFY)

Add `professional-travel` cases to existing generic module endpoints:

- `GET /modules/{unit}/{year}/professional-travel` → `get_module_data()`
- `GET /modules/{unit}/{year}/professional-travel/items` → `get_submodule_data()`
- `POST /modules/{unit}/{year}/professional-travel/items` → `create_travel(provider='manual')`
- `PATCH /modules/{unit}/{year}/professional-travel/items/{id}` → `update_travel()`
- `DELETE /modules/{unit}/{year}/professional-travel/items/{id}` → `delete_travel()`

**Files Summary**:

- **New**: 2 files (repository, service)
- **Modified**: 1 file (API router)

---

## Chapter 3: Module Configuration & Translations

### Goal

Set up frontend module configuration with field definitions and multilingual support.

### Module Configuration

**File**: `frontend/src/constant/module-config/professional-travel.ts` (NEW)

Create module config following existing patterns (Equipment, Headcount):

```typescript
export const professionalTravel: ModuleConfig = {
  id: "module_travel_001",
  type: "professional-travel",

  // Display settings
  hasDescription: true, // Shows subtitle
  hasDescriptionSubtext: true, // Shows supplementary instructions
  hasTooltip: true, // Shows (i) info button
  hasSubmodules: false, // No submodules (flat structure)
  formStructure: "single", // Single form (not per submodule)

  // Number formatting for totals
  numberFormatOptions: {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0, // No decimals for tonnes display
  },
  unit: "t CO₂-eq", // Display unit for totals

  // Red highlighting threshold
  threshold: {
    type: "fixed",
    value: 1000, // Highlight emissions > 1000 kg
  },

  // Table columns defined in Chapter 5
  moduleFields: [], // Will be populated

  // Form fields defined in Chapter 7
  formFields: [], // Will be populated
};
```

### Translation Keys

**Files**: `frontend/src/i18n/en-US/index.ts` and `frontend/src/i18n/fr-FR/index.ts` (MODIFY)

Add comprehensive translations for the module:

**Module Header** (Chapter 4):

- `professional-travel-title`: "Professional Travel" / "Voyages professionnels"
- `professional-travel-description`: Description about recording travel
- `professional-travel-description-subtext`: Instructions for manual train entry
- `professional-travel-tooltip`: "Information"
- `professional-travel-tooltip-content`: Tooltip explaining module purpose

**Table** (Chapter 5):

- `professional-travel-table-title`: "Trips" / "Voyages"
- `professional-travel-field-type`: "Type"
- `professional-travel-field-from`: "From" / "De"
- `professional-travel-field-to`: "To" / "À"
- `professional-travel-field-start-date`: "Start Date" / "Date de début"
- `professional-travel-field-number-trips`: "Number of trips" / "Nombre de trajets"
- `professional-travel-field-distance`: "Distance (km)"
- `professional-travel-field-traveler`: "Traveler" / "Voyageur"
- `professional-travel-field-emissions`: "kg CO₂-eq"

**Form** (Chapter 7):

- `professional-travel-form-title`: "Add a trip" / "Ajouter un voyage"
- `professional-travel-field-*`: Labels for all 10 form fields
- Button labels, placeholders, validation messages

**Totals** (Chapter 6):

- `module-total-in-progress`: Work in progress message
- `module-validate-button`: "Validate" / "Valider"
- `module-edit-button`: "Edit module" / "Modifier le module"

### Permission Integration

**File**: `frontend/src/utils/permission.ts` (Already exists)

The module is already mapped at line 317:

```typescript
[MODULES.ProfessionalTravel]: 'modules.professional_travel'
```

Use existing utilities:

- `hasPermission(permissions, 'modules.professional_travel', 'view')`: Module-level view check
- `hasPermission(permissions, 'modules.professional_travel', 'edit')`: Module-level edit check
- `getModulePermissionPath(MODULES.ProfessionalTravel)`: Get permission path dynamically

**Files Summary**:

- **New**: 1 file (module config)
- **Modified**: 2 files (i18n EN/FR)
- **No changes**: permission.ts (already configured)

---

## Chapter 4: Title Section

### Goal

Display module title, description, and supplementary text with info tooltip.

### Content Display

Based on specs from issue #18:

**Title** (Main heading):

- EN: "Professional Travel"
- FR: "Voyages professionnels"

**Subtitle** (Description):

- EN: "Record travel by plane and train, along with their associated emissions."
- FR: "Enregistrez les déplacements en avion et en train, ainsi que les émissions associées."

**Supplementary Text** (Instructions):

- EN: "Please manually complete all train trips. Plane trips are usually already listed in the table below."
- FR: "Veuillez renseigner manuellement tous les trajets en train. Les trajets en avion sont généralement déjà renseignés dans le tableau ci-dessous."

**Info Button** (Tooltip):

- Label: "Information" (both languages)
- Content: Explains module purpose and that API data may be pre-populated

### Component Integration

**No component changes needed**:

1. **`ModuleTitle.vue`** (already exists):
   - Reads `hasDescription`, `hasDescriptionSubtext`, `hasTooltip` from module config
   - Displays icon based on module type
   - Shows title from i18n key: `${moduleType}-title`
   - Shows description from i18n key: `${moduleType}-description`
   - Shows subtext from i18n key: `${moduleType}-description-subtext`
   - Renders info button with tooltip from i18n key: `${moduleType}-tooltip-content`

2. **`ModulePage.vue`** (already exists):
   - Includes `<ModuleTitle />` component at page top
   - Determines module type from route params
   - Automatically renders correct title when navigating to `/modules/.../professional-travel`

### Implementation

All implementation is in Chapter 3 (config + translations):

- Module config sets `hasDescription: true`, `hasDescriptionSubtext: true`, `hasTooltip: true`
- Translation files provide all text content
- Existing components handle rendering dynamically

**Files Summary**:

- **No new files** (relies on Chapter 3)
- **No component changes** (existing components handle this)

---

## Chapter 5: Table Section

### Goal

Display 8-column sortable/filterable table with permission-based actions and CSV operations.

### Table Structure

**Title**:

- EN: "Trips"
- FR: "Voyages"

**8 Columns Configuration**:

Add to `moduleFields` in module config:

```typescript
moduleFields: [
  {
    id: 'transport_mode',
    labelKey: 'professional-travel-field-type',
    type: 'select',
    options: ['flight', 'train'],
    sortable: true,
    required: true,
    ratio: '2/12',
    align: 'left',
  },
  {
    id: 'origin',
    labelKey: 'professional-travel-field-from',
    type: 'text',
    sortable: true,
    required: true,
    ratio: '3/12',
    align: 'left',
  },
  {
    id: 'destination',
    labelKey: 'professional-travel-field-to',
    type: 'text',
    sortable: true,
    required: true,
    ratio: '3/12',
    align: 'left',
  },
  {
    id: 'departure_date',
    labelKey: 'professional-travel-field-start-date',
    type: 'date',
    sortable: true,
    required: false,
    ratio: '2/12',
    align: 'left',
  },
  {
    id: 'number_of_trips',
    labelKey: 'professional-travel-field-number-trips',
    type: 'number',
    sortable: true,
    required: true,
    min: 1,
    ratio: '1/12',
    align: 'right',
  },
  {
    id: 'distance_km',
    labelKey: 'professional-travel-field-distance',
    type: 'number',
    sortable: true,
    unit: 'km',
    ratio: '2/12',
    align: 'right',
    editableInline: false,        // Auto-calculated
  },
  {
    id: 'traveler_name',
    labelKey: 'professional-travel-field-traveler',
    type: 'text',
    sortable: true,
    required: true,
    ratio: '3/12',
    align: 'left',
  },
  {
    id: 'kg_co2eq',
    labelKey: 'professional-travel-field-emissions',
    type: 'number',
    sortable: true,
    unit: 'kg CO₂-eq',
    ratio: '2/12',
    align: 'right',
    editableInline: false,        // Auto-calculated
  },
],
```

### Table Features

**Sorting** (already implemented):

- Click column header to toggle sort
- Updates URL: `?sort_by=kg_co2eq&sort_order=desc`
- Backend applies `ORDER BY` clause
- Works on all columns marked `sortable: true`

**Filtering** (already implemented):

- Search box for text input
- Searches: `traveler_name`, `origin`, `destination` (backend ILIKE)
- Updates URL: `?filter=paris`
- Real-time filtering as user types

**Pagination** (already implemented):

- Default: 20 items per page
- URL params: `?page=2&limit=20`
- Shows total count and page numbers
- Backend returns paginated results

**Edit/Delete Actions**:

- Show buttons only if `row.can_edit === true` (from backend)
- Edit button opens dialog with ModuleForm
- Delete button shows confirmation dialog
- Permission checks in service layer (Chapter 2)

**API Data Badge**:

- Cloud icon for `provider='api'` trips
- Badge text: "API"
- Tooltip: "Imported from external system (read-only)"
- No edit/delete buttons for API trips

**Red Highlighting**:

- Threshold: 1000 kg CO₂-eq
- Apply `text-red` class when `kg_co2eq > threshold.value`
- Visual indicator for high-emission trips
- Already supported by ModuleTable component

### CSV Operations

**Download CSV Template**:

Add to `ModuleTable.vue`:

```typescript
function downloadCSVTemplate() {
  const headers = [
    "Type",
    "From",
    "To",
    "Start Date",
    "Number of trips",
    "Traveler Name",
    "Class",
    "Purpose",
    "Notes",
  ];
  const csv = headers.join(",") + "\n";
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "professional-travel-template.csv";
  link.click();
}
```

**Upload CSV**:

- Links to issue #220 for UI implementation
- Backend endpoint: `POST /modules/{unit}/{year}/professional-travel/upload-csv`
- Full CSV import logic in Chapter 9

**Files Summary**:

- **Modified**: 1 file (module config for moduleFields), 1 file (ModuleTable for CSV template)

---

## Chapter 6: Total/Results Section

### Goal

Display aggregated CO2 emissions with validate/edit workflow for module state management.

### Calculation Logic

**Formula**:

```
Total (tonnes CO₂-eq) = SUM(all trips kg_co2eq) / 1000
Rounded to 0 decimal places
```

**Example**:

```
Trip 1: 1,250 kg
Trip 2: 850 kg
Trip 3: 3,400 kg
Total: (1250 + 850 + 3400) / 1000 = 5.5 → displays as "6 t CO₂-eq"
```

**User Filtering**:

- Std users: Sum only their trips (`WHERE created_by = user.id`)
- Principals/secondary: Sum all unit trips
- Applied in `get_summary_stats()` repository method

### Display States

**When NOT Validated** (in-progress):

- Hide total value
- Show message: "Work in progress, validate to see the results" (EN)
- Show message: "En cours jusqu'à validation" (FR)
- Display "Validate" button
- All sections editable

**When Validated**:

- Show total: "42 t CO₂-eq" (with 0 decimals)
- Display "Edit module" button
- All input sections greyed out
- Add/edit/delete buttons disabled

### Validation Workflow

**Validate Action** (locks module):

1. User clicks "Validate"
2. Frontend: `timelineStore.setState('validated')`
3. API call: `PATCH /timeline/{unit}/{year}/professional-travel/state`
4. Backend: Update timeline table
5. Frontend: Refresh module data
6. UI updates:
   - Total visible
   - Button → "Edit module"
   - Sections greyed
   - Actions disabled

**Edit Module Action** (unlocks module):

1. User clicks "Edit module"
2. Frontend: `timelineStore.setState('in-progress')`
3. API call to update state
4. UI unlocks:
   - Total hidden
   - Button → "Validate"
   - Sections enabled
   - Actions enabled

### Implementation

**Backend** (`professional_travel_service.py` - MODIFY):

Update `get_summary_stats()`:

```python
total_kg = float(row.total_kg_co2eq or 0.0)
total_tonnes = round(total_kg / 1000, 0)  # 0 decimals

return ModuleTotals(
    total_submodules=0,
    total_items=stats["total_items"],
    total_kg_co2eq=total_kg,
    total_tonnes_co2eq=total_tonnes,
    total_annual_fte=None,
    total_annual_consumption_kwh=None,
)
```

**Frontend** (module config - MODIFY):

Already added in Chapter 3:

```typescript
numberFormatOptions: {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
},
unit: 't CO₂-eq',
```

**No component changes needed**:

- `ModuleTotalResult.vue` handles all display logic
- `timelineStore` manages state transitions
- Backend timeline API already exists

**Files Summary**:

- **Modified**: 1 file (service for calculation)

---

## Chapter 7: Form & Input Section

### Goal

Implement 10-field form with custom From/To component and permission-based traveler filtering.

### Custom Component: TripRouteInput

**File**: `frontend/src/components/molecules/TripRouteInput.vue` (NEW)

**Design**:

- Two text inputs side-by-side (From | To)
- Swap button in middle with `swap_horiz` icon
- Clicking swap button reverses the two values
- Support for labels, placeholders, error messages
- Emits `update:from` and `update:to` events
- Responsive grid layout

**Props**:

- `from: string` - Origin value
- `to: string` - Destination value
- `errorFrom: string` - Validation error for origin
- `errorTo: string` - Validation error for destination
- `labelFrom: string` - Label for origin input
- `labelTo: string` - Label for destination input
- `placeholderFrom: string` - Placeholder text
- `placeholderTo: string` - Placeholder text

**Storybook Documentation**:

**File**: `frontend/src/components/molecules/TripRouteInput.stories.ts` (NEW)

Following `BigNumber.stories.ts` pattern with 5 stories:

1. **Default**: Empty inputs with labels
2. **WithValues**: Pre-filled with "Geneva" / "Paris"
3. **WithPlaceholders**: Show example placeholders "e.g., Geneva, GVA"
4. **WithErrors**: Display validation errors on both fields
5. **Interactive**: Demonstrate swap button functionality

Include JSDoc comments explaining:

- Purpose: Reversible route input for travel module
- Features: Swap button, validation, responsive layout
- Usage: How to handle events, pass errors

### Form Fields (10 total)

Add to `formFields` in module config:

1. **Type** (required):
   - Type: `select`
   - Options: `['flight', 'train']`
   - Label: "Type" / "Type"

2. **From/To** (required):
   - Type: `custom`
   - Component: `'TripRouteInput'`
   - Binds to `origin` and `destination` fields
   - Labels: "From" / "De", "To" / "À"

3. **Start Date** (optional):
   - Type: `date`
   - Label: "Start Date" / "Date de début"

4. **Return Date** (optional):
   - Type: `date`
   - Label: "Return Date" / "Date de retour"
   - Validation: Must be >= start date

5. **Round trip** (optional):
   - Type: `checkbox`
   - Label: "Round trip" / "Aller-retour"
   - If checked, backend creates 2 records

6. **Number of trips** (required):
   - Type: `number`
   - Default: 1
   - Min: 1
   - Label: "Number of trips" / "Nombre de trajets"

7. **Traveler** (required):
   - Type: `select`
   - Options: Dynamic from headcount
   - Label: "Traveler" / "Voyageur"
   - Filtered by permission (see below)

8. **Class** (optional):
   - Type: `select`
   - Conditional options based on transport_mode:
     - Flight: `['economy', 'economy_plus', 'business', 'first']`
     - Train: `['class_1', 'class_2']`
   - Label: "Class" / "Classe"
   - Clear value when transport_mode changes

9. **Purpose** (required):
   - Type: `textarea`
   - Label: "Purpose" / "Motif"
   - Max length: 500

10. **Notes** (optional):
    - Type: `textarea`
    - Label: "Notes"

### Traveler Dropdown Filtering

**File**: `frontend/src/stores/modules.ts` (MODIFY)

Add `getTravelers()` method:

```typescript
async getTravelers(unitId: string, year: number) {
  // Fetch members from headcount module
  const response = await api.get(`/modules/${unitId}/${year}/my-lab/items?submodule=member`);
  const members = response.data.items;

  // Check edit permission
  const hasEditPermission = hasPermission(
    userStore.permissions,
    'modules.professional_travel',
    PermissionAction.EDIT
  );

  // Filter to current user if no edit permission
  if (!hasEditPermission) {
    const currentUserId = userStore.user.id;
    return members
      .filter(m => m.cf_user_id === currentUserId)
      .map(m => ({ label: m.display_name, value: m.cf_user_id }));
  }

  // Return all members for principals/secondary
  return members.map(m => ({
    label: m.display_name,
    value: m.cf_user_id
  }));
}
```

Populate `dynamicOptions['travelers']` when form mounts.

### Form Integration

**File**: `frontend/src/components/organisms/module/ModuleForm.vue` (MODIFY)

Add support for custom components:

```typescript
// Detect custom component type
if (field.type === "custom" && field.component === "TripRouteInput") {
  return h(TripRouteInput, {
    from: form.origin,
    to: form.destination,
    "onUpdate:from": (value) => (form.origin = value),
    "onUpdate:to": (value) => (form.destination = value),
    errorFrom: errors.origin,
    errorTo: errors.destination,
  });
}
```

### Validation

**Client-side**:

- Required: transport_mode, origin, destination, number_of_trips, traveler_id, purpose
- Number: number_of_trips >= 1
- Date: return_date >= departure_date (if both provided)
- Logic: origin ≠ destination

**Backend** (in service):

- Traveler exists in HeadCount (`_validate_traveler()`)
- Valid transport_mode: 'flight' or 'train'
- Valid transport_class for given transport_mode
- All required fields present

### Form Submission Flow

1. User fills form, clicks "Add trip"
2. Frontend: Validate client-side
3. API call: `POST /modules/{unit}/{year}/professional-travel/items`
4. Backend:
   - Validate traveler
   - Calculate distance (Chapter 8)
   - Calculate CO2 emissions (Chapter 8)
   - Create record(s) (2 if round trip)
   - Return with `can_edit=true`
5. Frontend:
   - On success: Clear form, refresh table, show notification
   - On error: Show message, keep form data

**Files Summary**:

- **New**: 2 files (TripRouteInput component + stories)
- **Modified**: 3 files (module config for formFields, ModuleForm for custom component, store for getTravelers)

---

## Chapter 8: CO2 Calculation Logic

### Goal

Calculate distance and CO2 emissions for manual and CSV-imported trips (API trips already have calculations).

### When to Calculate

- **Manual entries** (`provider='manual'`): Always calculate
- **CSV imports** (`provider='csv'`): Always calculate
- **API data** (`provider='api'`): Skip calculation (use existing values)

### Flight Calculation

**Formula**:

```
kg_CO₂-eq = (Great_Circle_Distance + 95km) × Impact_Score × RFI × Class_Multiplier
```

**Distance Calculation**:

```
Distance(km) = Haversine(origin, destination) + 95
```

**Haul Categories** (determines impact score):

- Very short haul: < 800 km → 0.174 kg/km
- Short haul: 800-1500 km → 0.134 kg/km
- Medium haul: 1500-4000 km → 0.11 kg/km
- Long haul: > 4000 km → 0.108 kg/km

**RFI (Radiative Forcing Index)**: 2.7 (constant for all flights)

**Class Multipliers**:

- Economy: 1.0 (baseline)
- Economy Plus: 1.2
- Business: 2.0
- First: 3.0

**Example**:

```
Flight: Geneva (GVA) → Paris (CDG)
Distance: 410 km + 95 = 505 km
Category: Very short haul (< 800 km)
Impact Score: 0.174 kg/km
Class: Business (multiplier: 2.0)
RFI: 2.7

Calculation:
kg_CO₂ = 505 × 0.174 × 2.7 × 2.0 = 475.6 kg
```

### Train Calculation

**Formula**:

```
kg_CO₂-eq = (Great_Circle_Distance × 1.2) × Country_Impact_Score × Class_Multiplier
```

**Distance Calculation**:

```
Distance(km) = Haversine(origin, destination) × 1.2
```

**Geography Rules**:

1. If trip entirely in CH → use CH fleet average (0.004)
2. If trip crosses border → use destination country factor
3. If destination not in table → use RoW (Rest of World: 0.056)

**Country Impact Scores** (kg CO₂-eq/km):

- CH (Switzerland): 0.004
- FR (France): 0.007
- DE (Germany): 0.056
- IT (Italy): 0.029
- AT (Austria): 0.014
- RoW (Rest of World): 0.056

**Class Multipliers**:

- Class 2: 1.0 (baseline)
- Class 1: 1.5

**Example**:

```
Train: Geneva → Paris
Distance: 410 × 1.2 = 492 km
Geography: Border crossing (CH → FR)
Country Factor: FR (0.007 kg/km)
Class: Class 1 (multiplier: 1.5)

Calculation:
kg_CO₂ = 492 × 0.007 × 1.5 = 5.2 kg
```

### Implementation Files

**1. Emission Factors** (`backend/app/constants/emission_factors.py` - NEW):

```python
FLIGHT_EMISSION_FACTORS = {
    "very_short_haul": {"impact_score": 0.174, "rfi": 2.7, "max_km": 800},
    "short_haul": {"impact_score": 0.134, "rfi": 2.7, "max_km": 1500},
    "medium_haul": {"impact_score": 0.11, "rfi": 2.7, "max_km": 4000},
    "long_haul": {"impact_score": 0.108, "rfi": 2.7, "max_km": None},
}

FLIGHT_CLASS_MULTIPLIERS = {
    "economy": 1.0,
    "economy_plus": 1.2,
    "business": 2.0,
    "first": 3.0,
}

TRAIN_EMISSION_FACTORS = {
    "CH": 0.004,
    "FR": 0.007,
    "DE": 0.056,
    "IT": 0.029,
    "AT": 0.014,
    "RoW": 0.056,
}

TRAIN_CLASS_MULTIPLIERS = {
    "class_2": 1.0,
    "class_1": 1.5,
}
```

**2. Distance Calculation** (`backend/app/utils/geo.py` - NEW):

Haversine formula for great circle distance:

```python
from math import radians, sin, cos, sqrt, atan2

def calculate_great_circle_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate great circle distance in km using Haversine formula."""
    R = 6371  # Earth radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c
```

**3. Geocoding** (`backend/app/utils/geocoding.py` - NEW):

**Approach**: Local database (airports/stations CSV) with optional external API fallback

**Option A - Local Database** (recommended):

- Load airport/station coordinates from CSV files
- Query local database for coordinates
- Fast, no API dependencies

**Option B - External API** (fallback):

- Use OpenStreetMap Nominatim or Google Maps
- Handle rate limiting
- Cache results

**Locations Table** (`backend/app/models/locations.py` - NEW):

```sql
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE,        -- IATA code (airports) or name (stations)
    name VARCHAR(255),
    type VARCHAR(20),               -- 'airport' or 'station'
    latitude FLOAT,
    longitude FLOAT,
    country VARCHAR(2),             -- ISO country code
    INDEX idx_code (code),
    INDEX idx_name (name)
);
```

**Data Files**:

- `backend/data/airports.csv`: Major airports with IATA codes, coordinates
- `backend/data/stations.csv`: Major European train stations with coordinates

**4. Service Methods** (`professional_travel_service.py` - MODIFY):

Add calculation methods:

```python
def calculate_flight_emissions(
    origin: str,
    destination: str,
    transport_class: str,
    number_of_trips: int
) -> tuple[float, float]:
    """Calculate flight emissions. Returns (distance_km, kg_co2eq)"""
    # 1. Geocode origin and destination
    origin_coords = geocode_location(origin, type="airport")
    dest_coords = geocode_location(destination, type="airport")

    # 2. Calculate distance + 95km
    distance = calculate_great_circle_distance(
        origin_coords.lat, origin_coords.lon,
        dest_coords.lat, dest_coords.lon
    ) + 95

    # 3. Determine haul category
    category = get_haul_category(distance)

    # 4. Get emission factors
    factor = FLIGHT_EMISSION_FACTORS[category]
    impact_score = factor["impact_score"]
    rfi = factor["rfi"]

    # 5. Apply class multiplier
    class_multiplier = FLIGHT_CLASS_MULTIPLIERS.get(transport_class, 1.0)

    # 6. Calculate total
    kg_co2eq = distance * impact_score * rfi * class_multiplier * number_of_trips

    return (distance, kg_co2eq)

def calculate_train_emissions(
    origin: str,
    destination: str,
    transport_class: str,
    number_of_trips: int
) -> tuple[float, float]:
    """Calculate train emissions. Returns (distance_km, kg_co2eq)"""
    # 1. Geocode with country info
    origin_location = geocode_location(origin, type="station")
    dest_location = geocode_location(destination, type="station")

    # 2. Calculate distance × 1.2
    distance = calculate_great_circle_distance(
        origin_location.lat, origin_location.lon,
        dest_location.lat, dest_location.lon
    ) * 1.2

    # 3. Determine emission factor by geography
    if origin_location.country == "CH" and dest_location.country == "CH":
        impact_score = TRAIN_EMISSION_FACTORS["CH"]
    elif dest_location.country in TRAIN_EMISSION_FACTORS:
        impact_score = TRAIN_EMISSION_FACTORS[dest_location.country]
    else:
        impact_score = TRAIN_EMISSION_FACTORS["RoW"]

    # 4. Apply class multiplier
    class_multiplier = TRAIN_CLASS_MULTIPLIERS.get(transport_class, 1.0)

    # 5. Calculate total
    kg_co2eq = distance * impact_score * class_multiplier * number_of_trips

    return (distance, kg_co2eq)
```

Integrate in `create_travel()`:

```python
if provider_source in ['manual', 'csv']:
    if data.transport_mode == 'flight':
        distance, kg_co2eq = calculate_flight_emissions(...)
    elif data.transport_mode == 'train':
        distance, kg_co2eq = calculate_train_emissions(...)

    data.distance_km = distance
    data.kg_co2eq = kg_co2eq
```

### Error Handling

**Geocoding failures**:

- If location not found → return 422 error
- Suggest format: "Try 'Geneva, GVA' or 'Paris, CDG'"

**Missing factors**:

- Should never happen (use defaults)
- Log warning if unexpected values

**Files Summary**:

- **New**: 6 files (constants, geo utils, geocoding utils, locations model, 2 CSV data files)
- **Modified**: 1 file (service)

---

## Chapter 9: CSV Import & API Integration

### Goal

Enable bulk data import via CSV files and scheduled sync with external travel booking API.

### CSV Import

**Column Mapping** (from external system to our database):

- `Centre Financier` → `unit_id`
- `IN_Segment origin` → `origin`
- `IN_Segment destination` → `destination`
- `IN_Departure date` → `departure_date`
- `OUT_Distance_default` → `distance_km`
- `OUT_CO2_corrected` → `kg_co2eq`
- Additional columns as needed

**Modular Design** (supports both flight and train):

**Option A**: Transport type in CSV

- CSV includes `Type` column with "flight" or "train"
- Service reads column to set `transport_mode`
- Most explicit, no ambiguity

**Option B**: Infer from data

- Airport codes (3 letters) → flight
- City names → train
- Less reliable, requires heuristics

**Option C**: Endpoint parameter

- Separate uploads for flights vs trains
- Endpoint specifies transport_mode
- Simplest but requires multiple uploads for mixed data

**Recommended**: Option A (explicit column)

### CSV Import Service

**File**: `backend/app/services/csv_import_service.py` (NEW)

**Responsibilities**:

- Parse CSV file (handle encoding, delimiters)
- Validate structure (required columns present)
- Map external columns to internal fields
- Detect or read transport_mode
- Set `provider='csv'` for all records
- Batch insert (100 records/chunk)
- Return summary: success count, error count, validation errors

**Validation Rules**:

- Required columns: Centre Financier, IN_Segment origin, IN_Segment destination, OUT_CO2_corrected
- Optional columns: IN_Departure date, OUT_Distance_default
- Data types: Dates valid, numbers numeric, emissions > 0
- Unit exists in system
- Traveler resolution (if provided, verify exists)

**Batch Processing**:

- Process in chunks of 100 records
- Commit each chunk separately
- Continue on errors (don't abort entire import)
- Return detailed error report with row numbers

**Duplicate Prevention**:

- Match on: unit_id + traveler_id + origin + destination + departure_date + provider
- Strategy: Update if exists, insert if new
- Option to skip duplicates vs overwrite (query param)
- Log all overwrites for audit

### API Endpoint

**File**: `backend/app/api/v1/modules.py` (MODIFY)

Add CSV upload endpoint:

```
POST /modules/{unit_id}/{year}/professional-travel/upload-csv
```

**Request**:

- Multipart form data with CSV file
- Optional query param: `transport_mode` (flight/train)
- Optional query param: `overwrite_existing` (boolean)

**Response**:

```json
{
  "success_count": 45,
  "error_count": 3,
  "total_kg_co2eq_added": 12450.5,
  "total_distance_km_added": 28900.0,
  "errors": [
    { "row": 12, "error": "Invalid date format" },
    { "row": 23, "error": "Unit not found: ABC123" },
    { "row": 34, "error": "Traveler not in headcount" }
  ]
}
```

**Flow**:

1. Check user has edit permission for module
2. Parse uploaded CSV file
3. Call CSV import service
4. Return results summary
5. Frontend shows success message or error details

**UI Integration**: Link to issue #220 for upload button implementation

### External API Integration

**File**: `backend/app/integrations/travel_api.py` (NEW)

Connect to external travel booking system (issue #302):

**Responsibilities**:

- Connect to external API (authentication)
- Fetch travel data for specific unit and date range
- Transform API response to internal format
- Use same field mapping as CSV import
- Set `provider='api'` for all records
- Handle pagination (if API returns large datasets)
- Store last sync timestamp (avoid duplicates)

**Error Handling**:

- API connection failures: Log and retry
- Authentication errors: Alert admin
- Rate limiting: Backoff and retry
- Data format mismatches: Skip record and log
- Duplicate detection: Same strategy as CSV

**Modular Design**:

- Support multiple transport types in single API response
- Use same field mapping configuration as CSV
- Reuse validation and batch processing logic

### Scheduled Sync

**File**: `backend/app/tasks/travel_sync.py` (NEW)

Background job using Celery or similar:

**Schedule**: Daily at 2 AM (configurable per unit)

**Process**:

```python
@celery.task
def sync_travel_data():
    for unit in get_active_units():
        try:
            # Call external API
            travels = fetch_from_api(unit.id, year=current_year)

            # Import with provider='api'
            result = import_travels(travels, provider='api')

            # Update last sync timestamp
            update_last_sync(unit.id)

            # Log results
            log_sync_results(unit.id, result)

        except Exception as e:
            # Email admin on failure
            send_admin_alert(unit.id, error=e)
```

**Configuration** (environment variables):

- `TRAVEL_API_URL`: External API endpoint
- `TRAVEL_API_KEY`: Authentication credentials
- `TRAVEL_SYNC_ENABLED`: Enable/disable per unit
- `TRAVEL_SYNC_FREQUENCY`: cron expression (default: daily 2 AM)
