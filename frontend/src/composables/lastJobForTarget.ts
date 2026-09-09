import { TargetType } from '@/constant/ingestion';
import type {
  ImportRow,
  SyncJobResponse,
} from '@/stores/backofficeDataManagement';

/**
 * Which "last upload" a card / dialog reads for a given target type.
 * Leaf module (no store import) so the Playwright pure-function spec
 * can cover it — the references card used to be a fork that bypassed
 * this lookup entirely, hence the dedicated regression guard.
 */
export function lastJobForTarget(
  row: ImportRow,
  targetType: TargetType,
): SyncJobResponse | undefined {
  if (targetType === TargetType.FACTORS) return row.lastFactorJob;
  if (targetType === TargetType.REFERENCE_DATA) return row.lastReferenceJob;
  return row.lastDataJob;
}
