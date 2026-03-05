# Plan: Job History Panel + Per-Row Sync Progress

**TL;DR:** Extend the Pinia store to record all SSE updates per job in-memory. Show a collapsible "Job History" panel below the import table with full per-job detail (stats, row errors, raw JSON). Add an inline indeterminate progress bar per table row while that row's sync is active.

---

## Phase 1 — Store (`backofficeDataManagement.ts`)

1. Add `JobHistoryEntry` interface:
   ```ts
   interface JobHistoryEntry {
     jobId: number;
     labelKey: string; // i18n key for module name
     year: number;
     targetType: "data_entries" | "factors";
     moduleTypeId: number;
     startedAt: Date;
     completedAt?: Date;
     status: "in_progress" | "completed" | "failed";
     allUpdates: JobUpdatePayload[];
     latestPayload?: JobUpdatePayload;
   }
   ```
2. Add `jobHistory = ref<JobHistoryEntry[]>([])` reactive state
3. Update `subscribeToJobUpdates` signature with optional 4th param:

   ```ts
   jobMeta?: { labelKey: string; moduleTypeId: number; year: number; targetType: 'data_entries' | 'factors' }
   ```

   - On subscribe: push a new `JobHistoryEntry` with `status: 'in_progress'` to `jobHistory`
   - On each SSE message: find entry by `jobId`, push to `allUpdates`, update `latestPayload`
   - On COMPLETED (status=3): set `completedAt`, set `status = 'completed'`
   - On FAILED (status=4): set `completedAt`, set `status = 'failed'`

4. Add `clearJobHistory()` action: `jobHistory.value = []`
5. Add `getActiveJobForRow(moduleTypeId: number, year: number, targetType: 'data_entries' | 'factors'): JobHistoryEntry | undefined`
   — looks for the first entry with `status === 'in_progress'` matching the three keys; used to drive per-row UI binding
6. Expose all new state/actions in the store return

---

## Phase 2 — New component `JobHistoryPanel.vue`

Create `frontend/src/components/organisms/data-management/JobHistoryPanel.vue`

- Reads `dataManagementStore.jobHistory` directly (no props needed)
- "Clear history" button → calls `dataManagementStore.clearJobHistory()`
- Empty state when `jobHistory.length === 0`
- Each entry rendered as `q-expansion-item`:
  - **Header:** `$t(entry.labelKey)`, year, target type badge (`data_management_job_target_data_entries` / `_target_factors`), status badge (color: warning=in_progress, positive=completed, negative=failed), formatted `startedAt` timestamp
  - **Body:**
    - Stats row: `rows_processed`, `rows_skipped`, `row_errors_count` from `latestPayload?.meta`
    - `row_errors` list: "Row N: reason" for each error in `latestPayload?.meta?.row_errors`
    - "Show raw JSON" toggle → `<pre>` block with `JSON.stringify(latestPayload, null, 2)`

---

## Phase 3 — `AnnualDataImport.vue` updates

7. Add `uploadLabelKey = ref<string | null>(null)` local ref
8. Set `uploadLabelKey.value = row.labelKey` in both `openUploadCsvDialog` and `openUploadFactorsDialog`
9. Pass `jobMeta` (4th arg) to `subscribeToJobUpdates` call in `onFilesUploaded`:
   ```ts
   dataManagementStore.subscribeToJobUpdates(jobId, onCompleted, onFail, {
     labelKey: uploadLabelKey.value!,
     moduleTypeId: module_type_id,
     year,
     targetType: uploadTargetType.value,
   });
   ```
10. Add inline per-row progress in both Data and Factors cells:
    - Compute `activeJob = dataManagementStore.getActiveJobForRow(row.moduleTypeId, year, targetType)`
    - If `activeJob` is defined → show `q-linear-progress indeterminate` + `activeJob.latestPayload?.status_message` text below the upload buttons
    - Once `activeJob` clears (sync done), spinner disappears; history panel handles the final state
11. Add `<job-history-panel />` inside a `q-expansion-item` labeled `$t('data_management_job_history')` below the `q-markup-table`

---

## Phase 4 — i18n (`backoffice_data_management.ts`)

Add the following keys (EN + FR) to `frontend/src/i18n/en-US/backoffice_data_management.ts`:

| Key                                       | EN                              | FR                               |
| ----------------------------------------- | ------------------------------- | -------------------------------- |
| `data_management_job_history`             | Job History                     | Historique des imports           |
| `data_management_job_history_empty`       | No import jobs in this session. | Aucun import dans cette session. |
| `data_management_job_history_clear`       | Clear history                   | Effacer l'historique             |
| `data_management_job_status_in_progress`  | In progress                     | En cours                         |
| `data_management_job_status_completed`    | Completed                       | Terminé                          |
| `data_management_job_status_failed`       | Failed                          | Échoué                           |
| `data_management_job_rows_processed`      | Rows processed                  | Lignes traitées                  |
| `data_management_job_rows_skipped`        | Rows skipped                    | Lignes ignorées                  |
| `data_management_job_row_errors`          | Row errors                      | Erreurs de ligne                 |
| `data_management_job_show_raw`            | Show raw JSON                   | Afficher le JSON brut            |
| `data_management_job_hide_raw`            | Hide raw JSON                   | Masquer le JSON brut             |
| `data_management_job_target_data_entries` | Data entries                    | Données                          |
| `data_management_job_target_factors`      | Factors                         | Facteurs                         |
| `data_management_job_sync_in_progress`    | Sync in progress…               | Synchronisation en cours…        |

---

## Relevant Files

- `frontend/src/stores/backofficeDataManagement.ts` — Add `JobHistoryEntry`, `jobHistory`, `getActiveJobForRow`, `clearJobHistory`; update `subscribeToJobUpdates`
- `frontend/src/components/organisms/data-management/JobHistoryPanel.vue` — NEW component
- `frontend/src/components/organisms/data-management/AnnualDataImport.vue` — per-row progress + history panel
- `frontend/src/i18n/en-US/backoffice_data_management.ts` — new i18n keys

---

## Verification

1. Upload a CSV → inline spinner appears on that row while SSE stream is active
2. Sync completes → spinner disappears, history panel adds entry with green badge + stats
3. Sync fails → red entry with row errors list + raw JSON visible
4. "Clear history" empties the panel
5. `make lint` (frontend) passes with no TS/ESLint errors

---

## Decisions

- History is **in-memory only** (Pinia store), cleared on page refresh
- History panel is a **collapsible section** below the import table
- Progress is **per-row inline** (next to upload buttons), indeterminate only (backend doesn't emit percentage)
- No localStorage/sessionStorage persistence

## Out of Scope

- Persisting history across page refreshes
- Progress percentage (backend doesn't emit one)
- History for API-triggered syncs (same mechanism applies but not specifically tested)
