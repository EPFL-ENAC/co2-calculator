import { downloadFile } from '@/api/files';
import { lastJobForTarget } from '@/composables/lastJobForTarget';
import type { TargetType } from '@/constant/ingestion';
import type { ImportRow } from '@/stores/backofficeDataManagement';

// The one download path behind every upload card's arrow. The arrow only
// renders when the job has meta, so a missing path is a no-op, as before.
export async function downloadLastCsv(
  row: ImportRow,
  targetType: TargetType,
): Promise<void> {
  const job = lastJobForTarget(row, targetType);
  const filePath = (job?.meta as Record<string, unknown> | undefined)
    ?.processed_file_path;
  if (typeof filePath !== 'string' || filePath === '') return;
  await downloadFile(filePath);
}
