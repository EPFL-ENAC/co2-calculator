# Implementation Plan: Student FTE Calculator Helper

## Overview

Add calculator helper to student headcount form. Formula: `(students × duration × avg_fte) / 12 = Annual FTE`. Button adds result to Total Student FTE input.

## Requirements

1. Calculator component with 3 inputs + calculated result display
2. "Use This Value" button adds calculation to FTE field
3. Error handling for incomplete data
4. i18n support (EN/FR)

---

## Implementation Steps

### Frontend (2 files)

#### 1. Create Calculator Component

**File**: [frontend/src/components/organisms/module/StudentFTECalculator.vue](frontend/src/components/organisms/module/StudentFTECalculator.vue) (new)

**Template**:

- 3 number inputs: students, duration (months), avg FTE per student
- Computed display: "Calculated Annual FTE: X.XX"
- Button: "Use This Value" (disabled if inputs incomplete)

**Script**:

- Computed `calculatedFTE`: `(students × duration × avgFTE) / 12`
- Computed `isValid`: all 3 fields have values > 0
- `emits('use-value', calculatedFTE)` on button click

#### 2. Update Form Component

**File**: [frontend/src/components/organisms/module/ModuleForm.vue:18-26](frontend/src/components/organisms/module/ModuleForm.vue#L18-L26)
**Add method**:

```ts
function onUseCalculatedFTE(value: number) {
  form["fte"] = value;
}
```

---

## i18n Strings

**File**: [frontend/src/i18n/mylab.ts](frontend/src/i18n/mylab.ts)

Add keys:

- `student_helper_students_label`: "Number of students" / "Nombre d'étudiant·es"
- `student_helper_duration_label`: "Average duration (months)" / "Durée moyenne (mois)"
- `student_helper_avg_fte_label`: "Average FTE per student" / "EPT moyen par étudiant·e"
- `student_helper_calculated_label`: "Calculated Annual FTE" / "EPT annuel calculé"
- `student_helper_use_button`: "Use This Value" / "Utiliser cette valeur"

---

## Data Flow

1. User expands "Student FTE Calculator Helper"
2. Fills 3 inputs → calculation updates in real-time
3. Clicks "Use This Value" → `form['fte']` populated
4. User clicks "Update" → form submits with aggregated FTE

---

## Critical Files (3 total)

1. [frontend/src/components/organisms/module/StudentFTECalculator.vue](frontend/src/components/organisms/module/StudentFTECalculator.vue) (new)
2. [frontend/src/components/organisms/module/ModuleForm.vue](frontend/src/components/organisms/module/ModuleForm.vue)
3. [frontend/src/i18n/mylab.ts](frontend/src/i18n/mylab.ts)

---

## Success Criteria

✅ Calculator displays live calculation
✅ Button disabled when inputs incomplete
✅ Value populates FTE field on click
✅ i18n strings for EN/FR
