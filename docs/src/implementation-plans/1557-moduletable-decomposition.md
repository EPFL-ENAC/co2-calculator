---
status: delivered
issue: 1557
last_updated: 2026-07-16
title: "ModuleTable.vue decomposition"
summary: "Break the ~2017-line shared Calculator/planner data-entry table into composables + sub-components, each under the repo's 500-line limit, with no behavior change."
---

# ModuleTable.vue decomposition

Follow-up to [#1557](1557-planner-frontend-followups.md) — this fleshes out the
"`ModuleTable.vue` decomposition" section (A) into an ordered, shippable
sequence. The type-2 planner columns shipped first (2026-07-16, reordered from
the original prerequisite plan), so the decomposition now also moves the
reference/slider column wiring into a clean sub-component instead of the
2000-line file.

## Goal / rationale

- `frontend/src/components/organisms/module/ModuleTable.vue` is ~2017 lines —
  4× the repo's 500-line component limit.
- The file mixes column construction, inline-cell editing, note/edit/CSV/delete
  dialogs, pagination, expand watchers, and the new planner reference/slider
  column. None of it is unit-testable in isolation today.
- Extracting cohesive clusters into composables + sub-components makes each
  piece testable via Playwright CT and lets the planner columns sit in a small,
  reviewed surface.

## Constraints

- **No behavior change.** Pure structural move. The Calculator table must
  render and behave identically after every step.
- Reuse what exists — do **not** recreate dialogs:
  - `src/components/molecules/NoteDialog.vue` — already the note dialog
    template; keep it, extract only its driving state.
  - `src/components/molecules/EquipmentPowerFeedbackDialog.vue` — already the
    Equipment power-feedback dialog; keep it, reuse as-is.
- Each new file < 500 lines; core `ModuleTable.vue` ends < 500 too.
- Follow global style rules: `col()` n/a here (frontend), `type` narrowing over
  suppressions, no new patterns — mirror sibling composables in
  `src/composables/`.

## Extraction sequence

Each step is independently shippable and ends with the same check: **run the
Calculator, expand a module, screenshot the table, confirm no visual/behavioral
diff.** Ship steps as separate commits (or PRs) so a regression bisects cleanly.

### Step 1 — `useModuleTableColumns`

Extract column construction. Moves out of the script:

- `qCols` computed (base cols from `moduleFields`, planner reference/slider
  column injection under `showReferenceColumns`, trailing `action` col).
- `getColumnStyle`, `getColumnInputmode`, `getColumnTitle`, `getColumnRules`,
  `getColumnClasses`, `cellClasses`.
- `getNumericRules`, the `TableViewColumn` type.
- `taxonomyKindLabelMap`, `inlineOptionsMap`, `getInlineOptions`.

**Contract**

```ts
function useModuleTableColumns(params: {
  moduleFields: Ref<ModuleField[] | null>;
  submoduleType: Ref<EnumSubmoduleType>;
  showReferenceColumns: Ref<boolean>;
  showTableActions: Ref<boolean>;
  threshold: Ref<Threshold>;
}): {
  qCols: ComputedRef<TableViewColumn[]>;
  taxonomyKindLabelMap: ComputedRef<Record<string, string>>;
  inlineOptionsMap: ComputedRef<Record<string, Option[]>>;
  getInlineOptions: (col: TableViewColumn) => Option[];
  getColumnStyle: (col: TableViewColumn) => Record<string, string>;
  getColumnClasses: (row: ModuleRow, col: TableViewColumn) => unknown[];
  getColumnInputmode: (col: TableViewColumn) => string | undefined;
  getColumnTitle: (col: TableViewColumn) => string | undefined;
  getColumnRules: (col: TableViewColumn) => ValidationRule[];
};
```

Export `TableViewColumn` from the composable; `renderCell` (Step 2) imports it.

### Step 2 — `useInlineCellEditing`

Extract inline editing. Moves out:

- `commitInline`, `inlineErrors`, `errorKey`, `setError`, `getError`.
- `validateUsageHoursWeek`, `validateNumberOfTrips`.
- `renderCell` (reads `taxonomyKindLabelMap` / `inlineOptionsMap` from Step 1
  and `headcountMembersMap`).

**Contract**

```ts
function useInlineCellEditing(params: {
  moduleType: Ref<Module>;
  submoduleType: Ref<EnumSubmoduleType>;
  unitId: Ref<number>;
  year: Ref<string | number>;
  carbonReportId: Ref<number | undefined>;
  moduleConfig: Ref<ModuleConfig>;
  headcountMembersMap: Ref<Map<string, string>>;
  inlineOptionsMap: ComputedRef<Record<string, Option[]>>;
  taxonomyKindLabelMap: ComputedRef<Record<string, string>>;
}): {
  inlineErrors: Ref<Record<string, string>>;
  getError: (row: ModuleRow, col: { name: string }) => string;
  commitInline: (row: ModuleRow, col: TableViewColumn) => Promise<void>;
  renderCell: (row: ModuleRow, col: TableViewColumn) => string;
};
```

`commitInline` keeps calling `moduleStore.patchItem`; the composable owns the
store handle. Keep `setError` internal unless a caller needs it.

### Step 3 — `useModuleNoteDialog` (dialogs stay as existing molecules)

The note dialog **template already lives in `NoteDialog.vue`** and the power
dialog in `EquipmentPowerFeedbackDialog.vue` — do **not** add a
`ModuleNoteDialog.vue`. Extract only the state/handlers that drive them:

- `noteDialogOpen`, `noteDialogCurrentNote`, `noteDialogRowId`,
  `noteDialogMode`, `openNoteDialog`, `saveNote`, `deleteNote`.
- Power-feedback state: `powerFeedbackDialogOpen`, `powerFeedbackRow`,
  `isEquipmentModule` (routes `openNoteDialog` to the power dialog for
  Equipment).
- `noteButtonIcon`/`noteButtonColor`/`noteButtonStyle`/`noteButtonTextColor`.

**Contract**

```ts
function useModuleNoteDialog(params: {
  moduleType: Ref<Module>;
  submoduleType: Ref<EnumSubmoduleType>;
  unitId: Ref<number>;
  year: Ref<string | number>;
  carbonReportId: Ref<number | undefined>;
  moduleColor: Ref<string | undefined>;
  moduleColors: ComputedRef<ModuleIconColors>;
}): {
  noteDialogOpen: Ref<boolean>;
  powerFeedbackDialogOpen: Ref<boolean>;
  noteDialogCurrentNote: Ref<string>;
  noteDialogMode: ComputedRef<"add" | "edit">;
  powerFeedbackRow: Ref<PowerFeedbackRow>;
  openNoteDialog: (row: ModuleRow) => void;
  saveNote: (note: string) => Promise<void>;
  deleteNote: () => Promise<void>;
  noteButtonIcon: (note: unknown) => string;
  noteButtonColor: (note: unknown) => string | undefined;
  noteButtonStyle: (note: unknown) => Record<string, string> | undefined;
  noteButtonTextColor: (note: unknown) => string | undefined;
};
```

The `<NoteDialog>` and `<EquipmentPowerFeedbackDialog>` tags stay in the core
template, bound to these returns.

### Step 4 — `ModuleEditDialog.vue`

New sub-component for the edit dialog (template lines ~281–318) + its state.

- Owns: `editDialogOpen`, `editInputs`, `editRowData`, the reset watcher,
  `onFormSubmit`. Renders `<ModuleForm>` inside the `q-dialog`.

**Props / emits**

```ts
defineProps<{
  modelValue: boolean; // v-model:open
  moduleType: Module;
  submoduleType: EnumSubmoduleType;
  unitId: number;
  year: string | number;
  carbonReportId?: number;
  itemName: string;
  fields: ModuleField[] | null;
  rowData: Record<string, FieldValue> | null;
}>();
defineEmits<{ "update:modelValue": [boolean] }>();
```

Submit calls `postItem`/`patchItem` internally (moved from `onFormSubmit`), then
closes. Parent opens it by setting the model + passing `fields`/`rowData`.

### Step 5 — `ModuleCsvUploadDialog.vue`

New sub-component wrapping the CSV top-bar buttons + `FilesUploadDialog` + the
sync/SSE flow (`onUploadCsv`, `onDownloadTemplate`, `onFilesUploaded`,
`formatRowErrors`, the `onUnmounted` unsubscribe).

**Props / emits**

```ts
defineProps<{
  moduleType: Module;
  submoduleType: EnumSubmoduleType;
  unitId: number;
  year: string | number;
  carbonReportId?: number;
  disable: boolean;
}>();
defineEmits<{ synced: [] }>(); // parent refetches submodule + module data
```

Keeps the `dataManagementStore` subscription local; unsubscribes on unmount.
Emits `synced` so the parent (or the composable) triggers the existing refetch.

### Step 6 — core `ModuleTable.vue` slims to the table shell

After Steps 1–5, the core keeps only:

- The `q-table` with `header`/`body`/`pagination`/`no-data` slots and cell
  wiring (delegating to the returns above).
- `onRequest` (pagination), the expand + data watchers, `onMounted` (headcount
  preload), delete-confirm state (`confirmDelete`, `deleteRowId`,
  `onConfirmDelete`), `rowClasses` + the `isComplete*` helpers, prop/`computed`
  passthrough (`isDisabled`, `showTableActions`, etc.).
- Tags for `<ModuleEditDialog>`, `<ModuleCsvUploadDialog>`, `<NoteDialog>`,
  `<EquipmentPowerFeedbackDialog>`, delete `q-dialog`.

If the core is still > 500 after this, extract the `isComplete*` cluster into a
`useModuleRowCompleteness(moduleType, submoduleType, submoduleConfig)` composable
returning `isComplete(row)` / `rowClasses(row)` — it is self-contained and the
cheapest next cut.

## Risks & de-risking

| Area                | Risk                                                                         | De-risk                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Inline editing      | `commitInline` closure over `props`/store breaks when moved                  | Pass reactive refs into the composable; screenshot + edit a numeric cell (comma → error, dot → save) after Step 2                |
| Pagination          | `@request` reads/writes `moduleStore.state.paginationSubmodule` by ref       | Leave `onRequest` in the core (Step 6); it stays on the store, not the extracted pieces                                          |
| Expand watchers     | `immediate: true` watcher on `expandedSubmodules` + `onMounted` double-fetch | Keep both in the core untouched; verify a collapsed→expanded fetch still fires once                                              |
| Note / power dialog | Equipment routes to the power dialog; shared note state                      | Reuse existing molecules; test note save on a non-Equipment module and the power dialog on Equipment                             |
| Edit / CSV dialogs  | Moving state out of core loses the reset-on-close watcher / SSE unsubscribe  | Move the watcher into `ModuleEditDialog`, the `onUnmounted` unsubscribe into `ModuleCsvUploadDialog`                             |
| Planner slider      | `showReferenceColumns` injection + `onPercentageChange` PATCH                | Column injection goes to Step 1, `onPercentageChange` stays with the slider wiring; verify slider 40% → kg recomputes in planner |

**Standing de-risk:** screenshot the Calculator table (Equipment + Travel, which
exercise power dialog and `renderCell` name resolution) after **each** step and
diff against the pre-refactor baseline.

## Testing

Repo has Playwright unit CT + integration; **no vitest**. Add/extend CT mounts
for the extracted pieces where cheap (column building, inline validation
messages, note save). Rely on existing integration coverage for the full table;
the screenshot-per-step check is the primary safety net for "no behavior
change".

## Definition of done

- [ ] Each new file < 500 lines; core `ModuleTable.vue` < 500 lines.
- [ ] No behavior change — Calculator table verified after every step.
- [ ] `NoteDialog.vue` / `EquipmentPowerFeedbackDialog.vue` reused, not
      recreated.
- [ ] `make type-check` (vue-tsc) + lint green.
- [ ] Planner reference/slider column still renders and PATCHes in planner
      context.
