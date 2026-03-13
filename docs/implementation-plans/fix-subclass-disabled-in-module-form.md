# Fix: sub_class field disabled state in ModuleForm

## Bug

When an `equipment_class` (e.g. "3D printer") has an empty `sub_class` array from `/api/v1/factors/{id}/class-subclass-map`, the `sub_class` field should be hidden/disabled. This worked in `ModuleTable` (via `ModuleInlineSelect.vue`) but **not** in `ModuleForm.vue` — the form showed an empty required `<q-select>`, blocking submission.

## Root Cause

- **`ModuleInlineSelect.vue` (table):** checks `subClassOptions.length === 0` and renders a placeholder `<div>` instead of the select. Correct behavior.
- **`ModuleForm.vue` (form):** only checked `disableUntilField` (a prop not used by equipment config). Had **no check** for empty subkind options → always rendered the select, even when empty.

## Changes

### File: `frontend/src/components/organisms/module/ModuleForm.vue`

### 1. Template — placeholder when subkind options are empty

Extended the existing `disableUntilField` placeholder condition to also trigger when `optionsId === 'subkind'` and the filtered options list is empty (and not loading):

```html
<template
  v-if="
    (inp.disableUntilField && !form[inp.disableUntilField]) ||
    (inp.optionsId === 'subkind' &&
      !loadingSubclasses &&
      (filteredOptionsMap[inp.id]?.length ?? 0) === 0)
  "
>
  <div class="subclass-placeholder" />
</template>
```

### 2. Validation — skip required check for empty subkind

Added a guard in `validateField()` before the `required` check to skip validation when the subkind field has no available options:

```ts
if (
  i.optionsId === "subkind" &&
  (filteredOptionsMap.value[i.id]?.length ?? 0) === 0
) {
  return true;
}
```

### No other files changed

- `equipment-electric-consumption.ts`: `sub_class.required = true` is correct for classes that have sub-classes.
- `useEquipmentClassOptions.ts`: already returns `[]` when no sub-classes exist.
- `ModuleInlineSelect.vue`: already handles this correctly in the table.

## Verification

1. Select "3D printer" (empty sub_class) in the form → sub_class shows placeholder, not an empty select
2. Submit the form → succeeds without sub_class validation error
3. Select a class with sub-classes → sub_class select appears and is required
4. Edit an existing row with sub-classes → sub_class remains editable and validated
