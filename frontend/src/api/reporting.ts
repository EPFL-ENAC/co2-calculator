import { api } from 'src/api/http';
import { MODULE_STATES } from 'src/constant/moduleStates';

export type ReportFormat = 'csv' | 'pdf';
export type ReportType = 'usage' | 'results' | 'combined' | 'detailed';

export interface ReportExportQueryParams {
  type: ReportType;
  years?: number[];
}

export interface ReportingStats {
  [MODULE_STATES.Default]: number;
  [MODULE_STATES.InProgress]: number;
  [MODULE_STATES.Validated]: number;
}

export async function exportReport(
  params: ReportExportQueryParams,
  format: ReportFormat,
): Promise<Blob> {
  return api
    .get('backoffice/export', {
      searchParams: { ...params, format },
    })
    .blob();
}
