import { useI18n } from 'vue-i18n';
import {
  TargetType,
  IngestionResult,
} from 'src/stores/backofficeDataManagement';
import type {
  ImportRow,
  SyncJobResponse,
} from 'src/stores/backofficeDataManagement';

export function useUploadCard() {
  const { t } = useI18n();

  const QUASAR_COLOR_MAP: Record<string, string> = {
    accent: 'var(--q-accent)',
    positive: 'var(--q-positive)',
    negative: 'var(--q-negative)',
    warning: 'var(--q-warning)',
    'grey-4': '#bdbdbd',
  };

  function cardStyle(color: string): string {
    if (color === 'positive') {
      const c = QUASAR_COLOR_MAP['positive'];
      return `border: 1px solid ${c}; background-color: color-mix(in srgb, ${c} 10%, transparent)`;
    }
    return 'border: 1px solid rgba(0,0,0,0.12)';
  }

  function dataButtonColor(row: ImportRow): string {
    if (row.isDisabled) return 'grey-4';
    if (!row.lastDataJob) return 'accent';
    if (row.lastDataJob.result === IngestionResult.ERROR) return 'negative';
    if (row.lastDataJob.result === IngestionResult.WARNING) return 'warning';
    return 'positive';
  }

  function factorButtonColor(row: ImportRow): string {
    if (row.isDisabled) return 'grey-4';
    if (!row.lastFactorJob) return 'accent';
    if (row.lastFactorJob.result === IngestionResult.ERROR) return 'negative';
    if (row.lastFactorJob.result === IngestionResult.WARNING) return 'warning';
    return 'positive';
  }

  function dataButtonLabel(row: ImportRow): string {
    if (row.isDisabled) return '';
    return row.lastDataJob
      ? t('data_management_reupload_data')
      : t('data_management_add_data');
  }

  function factorButtonLabel(row: ImportRow): string {
    if (row.isDisabled) return '';
    return row.lastFactorJob
      ? t('data_management_reupload_factors')
      : t('data_management_add_factors');
  }

  function safeFileName(meta: unknown): string | undefined {
    const fp = (meta as Record<string, unknown>)?.file_path as
      | string
      | undefined;
    if (!fp) return undefined;
    const parts = fp.split('/');
    return parts.length ? parts[parts.length - 1] : fp;
  }

  function downloadLastCsv(row: ImportRow, targetType: TargetType): void {
    const job =
      targetType === TargetType.DATA_ENTRIES
        ? row.lastDataJob
        : row.lastFactorJob;
    if (!job?.meta) return;
    const filePath = (job.meta as Record<string, unknown>)
      .processed_file_path as string;
    if (!filePath) return;
    const a = document.createElement('a');
    // ``?d=true`` flips the backend into download mode — it sets
    // ``Content-Disposition: attachment; filename="…"`` which is the
    // authoritative source for the saved filename in every browser.
    // Without it, Safari ignored ``a.download`` and saved the file
    // with the URL's last segment stripped of its extension
    // (regression reported 2026-05-21: ``equipments_data`` instead
    // of ``equipments_data.csv``).
    a.href = `/api/v1/files/${filePath}?d=true`;
    a.download = filePath.split('/').pop() || filePath;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function getJobInfo(job?: SyncJobResponse): {
    fileName: string | undefined;
    rowsProcessed: number | undefined;
    timestamp: Date | undefined;
  } {
    if (!job?.meta)
      return {
        fileName: undefined,
        rowsProcessed: undefined,
        timestamp: undefined,
      };

    const fileName = safeFileName(job.meta);
    const rowsProcessed = (job.meta as Record<string, unknown>)
      ?.rows_processed as number | undefined;
    const timestampStr = (job.meta as Record<string, unknown>)?.timestamp as
      | string
      | undefined;
    const timestamp = timestampStr ? new Date(timestampStr) : undefined;

    return { fileName, rowsProcessed, timestamp };
  }

  function hasErrorOrWarning(job?: SyncJobResponse): boolean {
    if (!job) return false;
    return (
      job.result === IngestionResult.WARNING ||
      job.result === IngestionResult.ERROR
    );
  }

  function getErrorDetails(job?: SyncJobResponse): {
    message: string;
    error?: string;
    stats?: Record<string, unknown>;
  } {
    if (!job) return { message: '' };

    const meta = job.meta as Record<string, unknown> | undefined;
    return {
      message: job.status_message || '',
      error: meta?.error as string | undefined,
      stats: meta?.stats as Record<string, unknown> | undefined,
    };
  }

  function getButtonColor(row: ImportRow, targetType: TargetType): string {
    if (targetType === TargetType.DATA_ENTRIES) {
      return dataButtonColor(row);
    }
    return factorButtonColor(row);
  }

  function getButtonLabel(row: ImportRow, targetType: TargetType): string {
    if (targetType === TargetType.DATA_ENTRIES) {
      return dataButtonLabel(row);
    }
    return factorButtonLabel(row);
  }

  return {
    cardStyle,
    dataButtonColor,
    factorButtonColor,
    dataButtonLabel,
    factorButtonLabel,
    safeFileName,
    downloadLastCsv,
    getJobInfo,
    hasErrorOrWarning,
    getErrorDetails,
    getButtonColor,
    getButtonLabel,
  };
}
