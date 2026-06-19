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

export function applyUnitFiltersToParams(
  searchParams: URLSearchParams,
  unitFilters: UnitFilters,
  withModules: boolean = true,
): void {
  if (unitFilters.path_affiliation) {
    unitFilters.path_affiliation.forEach((v) =>
      searchParams.append('path_affiliation', String(v)),
    );
  }
  if (unitFilters.path_lvl4) {
    unitFilters.path_lvl4.forEach((v) =>
      searchParams.append('path_lvl4', String(v)),
    );
  }
  if (
    unitFilters.overall_status !== undefined &&
    unitFilters.overall_status !== null &&
    unitFilters.overall_status !== ''
  ) {
    searchParams.append('overall_status', String(unitFilters.overall_status));
  }
  if (unitFilters.search) {
    searchParams.append('search', unitFilters.search);
  }
  if (withModules && unitFilters.modules && unitFilters.modules.length > 0) {
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
  const searchParams = new URLSearchParams({ format });
  applyUnitFiltersToParams(searchParams, unitFilters);

  return api.get('backoffice/report/usage', { searchParams }).blob();
}

export async function downloadDetailedReportFile(
  unitFilters: UnitFilters,
  format: ReportFormat,
): Promise<Blob> {
  if (format === 'pdf') {
    throw new Error('PDF format is not supported for detailed report');
  }
  const searchParams = new URLSearchParams({ format });
  applyUnitFiltersToParams(searchParams, unitFilters);

  return api.get('backoffice/report/detailed', { searchParams }).blob();
}

export async function downloadResultsReportFile(
  unitFilters: UnitFilters,
  format: ReportFormat,
): Promise<Blob> {
  if (format === 'pdf') {
    throw new Error('PDF format is not supported for results report');
  }
  const searchParams = new URLSearchParams({ format });
  applyUnitFiltersToParams(searchParams, unitFilters, false);

  return api.get('backoffice/report/results', { searchParams }).blob();
}
