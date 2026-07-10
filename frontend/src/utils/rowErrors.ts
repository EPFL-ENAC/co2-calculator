import type { JobRowError } from 'src/stores/backofficeDataManagement';
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';

/**
 * Cap on how many individual row-error lines a CSV upload result renders.
 * Beyond this, a single "... and N more error(s)" summary line is appended
 * instead of an ever-growing list.
 */
export const MAX_DISPLAYED_ROW_ERRORS = 5;

/**
 * Translate function shape expected from `useI18n()`'s `t` — kept minimal
 * so this stays a plain (non-Vue) utility and is trivial to unit test.
 */
type Translate = (key: string, params?: Record<string, unknown>) => string;

export interface MissingSyncedUnitErrorGroup {
  rowsSkipped: number;
  units: Array<{ unitInstitutionalId: string; rowCount: number }>;
}

/**
 * Collapse repeated unresolved-unit errors into the list an operator needs to
 * reconcile after the unit sync. If other error types are present, retain the
 * exact count only for the entries recorded in this group.
 */
export function groupMissingSyncedUnitErrors(
  rowErrors: JobRowError[] | undefined,
  rowErrorsCount: number | undefined,
): MissingSyncedUnitErrorGroup | undefined {
  const errors = rowErrors ?? [];
  const matching = errors.filter(
    (error) =>
      error.type === 'missing_synced_unit' && error.unit_institutional_id,
  );
  if (matching.length === 0) return undefined;

  const unitCounts = new Map<string, number>();
  for (const error of matching) {
    const unit = error.unit_institutional_id as string;
    unitCounts.set(unit, (unitCounts.get(unit) ?? 0) + 1);
  }

  return {
    rowsSkipped:
      matching.length === errors.length
        ? (rowErrorsCount ?? matching.length)
        : matching.length,
    units: Array.from(unitCounts, ([unitInstitutionalId, rowCount]) => ({
      unitInstitutionalId,
      rowCount,
    })),
  };
}

/**
 * Format a CSV/data-ingestion job's per-row validation errors into
 * human-readable lines ("Row 3: co2_factor: Input should be a valid
 * number (got 'abc')"), capped at {@link MAX_DISPLAYED_ROW_ERRORS} with a
 * trailing "... and N more error(s)" summary when there are more.
 *
 * Shared between `ModuleTable.vue` (which reads `payload.meta.row_errors`
 * off the live SSE job stream) and `useUploadCard.ts` (which reads
 * `job.meta.stats.row_errors` off the persisted job record) so both CSV
 * upload surfaces render the same reasons instead of one of them dumping
 * the raw backend payload.
 *
 * @param rowErrors - Row-level errors, e.g. `payload.meta.row_errors`.
 * @param rowErrorsCount - Total error count (may exceed `rowErrors.length`
 *   when the backend caps how many row errors it records); falls back to
 *   `rowErrors.length` when not provided.
 * @param t - Translate function (`useI18n()`'s `t`).
 * @returns Formatted lines, or an empty array when there are no row errors.
 */
export function formatRowErrorLines(
  rowErrors: JobRowError[] | undefined,
  rowErrorsCount: number | undefined,
  t: Translate,
): string[] {
  const errors = rowErrors ?? [];
  if (errors.length === 0) return [];

  const totalErrorCount = rowErrorsCount ?? errors.length;
  const lines = errors.slice(0, MAX_DISPLAYED_ROW_ERRORS).map((e) => {
    let reason = e.reason;

    // Special handling for headcount duplicate institutional ID error to
    // provide a more user-friendly message.
    if (reason === 'DUPLICATE_INSTITUTIONAL_ID') {
      reason = t('headcount-member-error-duplicate-uid', {
        label:
          typeof INSTITUTIONAL_ID_LABEL !== 'undefined'
            ? INSTITUTIONAL_ID_LABEL
            : '',
      });
    }
    return t('csv_sync_row_error', { row: e.row, reason });
  });

  if (totalErrorCount > MAX_DISPLAYED_ROW_ERRORS) {
    const displayedErrorCount = Math.min(
      errors.length,
      MAX_DISPLAYED_ROW_ERRORS,
    );
    lines.push(
      t('csv_sync_and_more_errors', {
        count: totalErrorCount - displayedErrorCount,
      }),
    );
  }

  return lines;
}
