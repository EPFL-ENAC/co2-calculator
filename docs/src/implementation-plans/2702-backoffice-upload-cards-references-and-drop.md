---
status: delivered
issue: 2702
last_updated: 2026-09-09

title: "Issue 2702 — References upload through the shared import dialog; upload cards accept a dropped CSV"
summary: "The references card in the backoffice configuration page was a 480-line fork of the shared UploadCard with a hidden file input that uploaded on selection, bypassing the import dialog's overwrite warning and the year-sync guard. It is now a thin wrapper routed through the same dialog as Factors and Data. Every upload card is also a drop zone: dropping a CSV uploads it straight away through the dialog's upload path, with no modal. Enter after picking a file in the dialog triggers Save."
---

# Issue 2702 — References upload through the shared import dialog; upload cards accept a dropped CSV

## Problem

1. Clicking "Upload Reference" opened the native file picker and uploaded
   immediately. Factors, Data and Reduction objectives open the import
   dialog first. `UploadCardReferences.vue` (from the original #741 work)
   re-implemented card style, job info, error details and download
   locally, so it never got the year-sync guard (#867), the pipeline
   phase label, or the abort button that the shared card gained since.
2. Uploading a CSV took five gestures: button, dialog, file field, picker,
   Save.

## Delivered

- `UploadCardReferences.vue` mirrors `UploadCardFactors.vue`: a wrapper
  around `UploadCard.vue` emitting `upload` with `TargetType.REFERENCE_DATA`.
  `SubmoduleItem.vue` routes it through the injected `openDataEntryDialog`
  like its siblings. Net: about 400 lines deleted.
- `lastJobForTarget(row, targetType)` (leaf module) is the single lookup
  for "last job of this target type", used by the dialog's overwrite
  warning and the three `downloadLastCsv` copies. `TargetType` moved to
  `constant/ingestion.ts` (re-exported from the store) so pure specs can
  import it.
- `UploadCard.vue` handles `dragenter` / `dragover` / `drop` on the card
  and shows a dashed "Drop CSV here" overlay while a file hovers. The
  overlay covers every child so `dragleave` fires only when the cursor
  leaves the card. Disabled cards ignore drops. The dropped file rides
  the existing `upload` event as an optional third argument.
- Both dialog openers (`DataManagementPage.vue` for reduction objectives,
  `ModuleConfig.vue` for module and submodule cards) accept the file and
  pass it as `dropFile`; `DataEntryDialogContent.vue` then runs its
  `uploadFiles()` path without showing the dialog and releases the
  parent's v-model. Follow-up (PR after #2703): the first cut opened the
  dialog pre-filled; the maintainer chose the Gmail-style direct upload,
  accepting that a drop skips the overwrite warning.
- Enter in the dialog: QFile owns Enter (it re-opens the picker), so
  after a pick the dialog moves focus to the Save button and Enter
  clicks it natively.
- The pipeline-scoping computeds moved unchanged from `UploadCard.vue`
  into `useCardPipelineScope.ts` to keep the component under 500 lines.
- `FileObject` (a `Blob` with a fictional `path`) is gone; the files
  store takes browser `File` objects, which is what `q-file` emits.
- i18n: `REFERENCE_DATA` dialog title noun and
  `data_management_drop_csv_here`, en and fr.

## Tests

- `tests/unit/last-job-for-target.spec.ts` — pure lookup per target type.
- `tests/integration/data-management.spec.ts` 5c — references upload
  through the dialog dispatches `target_type: 3`.
- 5d — a synthetic drop on the headcount factors card dispatches without
  opening the dialog.
- 5e — Enter after picking a file dispatches.
- 5f — a drop on a reduction-objective card carries the file and the
  `reduction_objective_type_id`.

The e2e suite serves the prebuilt `dist/spa`; run `quasar build` before
`npm run test:e2e` or the tests exercise the previous bundle.
