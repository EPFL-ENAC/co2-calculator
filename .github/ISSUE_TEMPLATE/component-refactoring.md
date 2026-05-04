# Refactor Large Frontend Components (>500 Lines)

## Overview

This issue tracks the refactoring of frontend components that exceed the 500-line limit defined in our coding standards. Large components are harder to maintain, test, and reuse.

## Component Size Policy

- **Limit**: Components must be ≤500 lines
- **Warning Threshold**: Plan refactoring when approaching 400 lines
- **Exceptions**: Chart components may exceed limit with justification

Reference: `.github/instructions/co2-calculator-rules.md.instructions.md`

## Components Requiring Refactoring

### Critical (>1000 lines)

| Component                        | Lines | Priority  | Suggested Split                                              |
| -------------------------------- | ----- | --------- | ------------------------------------------------------------ |
| `ModuleTable.vue`                | 1563  | 🔴 High   | Extract row components, filtering logic, pagination          |
| `ModuleCarbonFootprintChart.vue` | 1399  | 🟡 Medium | Extract chart sub-components, data transformation composable |
| `ModuleForm.vue`                 | 1084  | 🔴 High   | Extract form sections, validation logic, field components    |

### High (700-1000 lines)

| Component                         | Lines | Priority  | Suggested Split                                  |
| --------------------------------- | ----- | --------- | ------------------------------------------------ |
| `AdditionalCategoriesSection.vue` | 770   | 🟡 Medium | Extract category form, table, validation         |
| `ModuleConfig.vue`                | 741   | 🟢 Low    | Already partially refactored, clean up remaining |

### Medium (500-700 lines)

| Component                           | Lines | Priority | Suggested Split                                  |
| ----------------------------------- | ----- | -------- | ------------------------------------------------ |
| `DataEntryDialog.vue`               | 624   | 🟢 Low   | Extract upload cards, job handling logic         |
| `CarbonFootPrintPerPersonChart.vue` | 582   | 🟢 Low   | Extract chart helpers, data formatting           |
| `SubmoduleConfig.vue`               | 504   | 🟢 Low   | Already partially refactored, clean up remaining |

## Refactoring Strategy

### 1. Extract Business Logic → Composables

```
useModuleTable.ts    # Filtering, sorting, pagination
useChartData.ts      # Data transformations
useFormValidation.ts # Validation logic
```

### 2. Extract UI Patterns → Molecules

```
molecules/
  TableRow.vue       # Table row component
  ChartLegend.vue    # Chart legend
  FormField.vue      # Reusable form field
```

### 3. Split Complex Templates → Sub-components

```
organisms/
  ModuleTableFilters.vue
  ModuleTablePagination.vue
  ModuleFormSection.vue
```

## Success Criteria

- [ ] All components ≤500 lines (except justified chart components)
- [ ] Business logic extracted to composables
- [ ] Reusable UI extracted to molecules
- [ ] Unit tests for extracted composables
- [ ] No regression in functionality
- [ ] Pre-commit hook warns on new large components

## Implementation Notes

- Pre-commit hook now warns on components >500 lines
- Use `rtk wc -l <file>` to check component sizes
- Reference successful refactoring: `UploadCard*` components from data-management

## Related

- #780 - Data management refactoring (UploadCard examples)
- Coding standards: `.github/instructions/co2-calculator-rules.md.instructions.md`
