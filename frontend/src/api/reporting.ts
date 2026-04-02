import { api } from 'src/api/http';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { type UnitFilters } from 'src/stores/backoffice';

export type ReportFormat = 'csv' | 'pdf' | 'json';
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
  const searchParams = new URLSearchParams({
    type: params.type,
    format,
  });

  if (params.years) {
    params.years.forEach((year) => searchParams.append('years', String(year)));
  }

  return api.get('backoffice/export', { searchParams }).blob();
}

function _applyReportFilters(
  searchParams: URLSearchParams,
  unitFilters: UnitFilters,
): void {
  if (unitFilters.path_lvl2) {
    unitFilters.path_lvl2.forEach((v) =>
      searchParams.append('path_lvl2', String(v)),
    );
  }
  if (unitFilters.path_lvl3) {
    unitFilters.path_lvl3.forEach((v) =>
      searchParams.append('path_lvl3', String(v)),
    );
  }
  if (unitFilters.path_lvl4) {
    unitFilters.path_lvl4.forEach((v) =>
      searchParams.append('path_lvl4', String(v)),
    );
  }
  if (
    unitFilters.completion_status !== undefined &&
    unitFilters.completion_status !== ''
  ) {
    searchParams.append(
      'completion_status',
      String(unitFilters.completion_status),
    );
  }
  if (unitFilters.search) {
    searchParams.append('search', unitFilters.search);
  }
  if (unitFilters.modules && unitFilters.modules.length > 0) {
    unitFilters.modules.forEach((v) =>
      searchParams.append(
        'modules',
        `${v.module.replaceAll('-', '_')}:${v.state}`,
      ),
    );
  }
  if (unitFilters.years) {
    unitFilters.years.forEach((year) =>
      searchParams.append('years', String(year)),
    );
  }
}

export async function downloadUsageReportFile(
  unitFilters: UnitFilters,
  format: ReportFormat,
): Promise<Blob> {
  if (format === 'pdf') {
    throw new Error('PDF format is not supported for usage report');
  }
  const searchParams = new URLSearchParams({
    format,
  });
  _applyReportFilters(searchParams, unitFilters);

  return api.get('backoffice/report/usage', { searchParams }).blob();
}

export async function downloadDetailedReportFile(
  unitFilters: UnitFilters,
  format: ReportFormat,
): Promise<Blob> {
  if (format === 'pdf') {
    throw new Error('PDF format is not supported for detailed report');
  }
  const searchParams = new URLSearchParams({
    format,
  });
  _applyReportFilters(searchParams, unitFilters);

  return api.get('backoffice/report/detailed', { searchParams }).blob();
}
