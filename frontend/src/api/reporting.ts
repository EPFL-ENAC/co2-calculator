import { api } from 'src/api/http';

export type ReportFormat = 'csv' | 'pdf';
export type ReportType = 'usage' | 'results' | 'combined' | 'detailed';

export interface ReportExportQueryParams {
  type: ReportType;
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
