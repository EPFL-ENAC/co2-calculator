/**
 * Regression guard for ``lastJobForTarget``: the references card used to
 * be a fork with its own hidden file input, so the shared dialog never
 * saw ``lastReferenceJob`` (no overwrite warning, no year-sync guard).
 * Every target type now resolves through this one lookup.
 */
import { test, expect } from '@playwright/test';
import { lastJobForTarget } from '../../src/composables/lastJobForTarget';
import { TargetType } from '../../src/constant/ingestion';
import type {
  ImportRow,
  SyncJobResponse,
} from '../../src/stores/backofficeDataManagement';

const job = (id: number) => ({ job_id: id }) as SyncJobResponse;
const row = {
  lastDataJob: job(1),
  lastFactorJob: job(2),
  lastReferenceJob: job(3),
} as ImportRow;

test('each target type reads its own last job', () => {
  expect(lastJobForTarget(row, TargetType.DATA_ENTRIES)?.job_id).toBe(1);
  expect(lastJobForTarget(row, TargetType.FACTORS)?.job_id).toBe(2);
  expect(lastJobForTarget(row, TargetType.REFERENCE_DATA)?.job_id).toBe(3);
});

test('a row without a reference upload yields undefined, not a sibling job', () => {
  const noRef = { lastDataJob: job(1), lastFactorJob: job(2) } as ImportRow;
  expect(lastJobForTarget(noRef, TargetType.REFERENCE_DATA)).toBeUndefined();
});
