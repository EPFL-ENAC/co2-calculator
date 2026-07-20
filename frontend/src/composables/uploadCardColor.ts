import { IngestionResult } from 'src/constant/ingestion';

/**
 * Pure color decision for the data-upload button (leaf module so the
 * Playwright pure-function spec can import it — Issue #1216 + stage
 * incident 2026-07-17). CSV result takes precedence (an errored CSV
 * after a prior API success stays red); an API sync gets the same
 * ERROR/WARNING/SUCCESS mapping as a CSV upload — a WARNING API sync
 * (rows landed, some skipped) previously fell through to ``accent``
 * and the card read as "no data" despite thousands of imported rows.
 * An unrecognised result falls through to ``accent`` rather than
 * silently going green.
 */
export function resolveDataButtonColor(
  dataResult?: IngestionResult,
  apiResult?: IngestionResult,
): string {
  if (dataResult === IngestionResult.ERROR) return 'negative';
  if (dataResult === IngestionResult.WARNING) return 'warning';
  if (dataResult === IngestionResult.SUCCESS) return 'positive';
  if (apiResult === IngestionResult.ERROR) return 'negative';
  if (apiResult === IngestionResult.WARNING) return 'warning';
  if (apiResult === IngestionResult.SUCCESS) return 'positive';
  return 'accent';
}
