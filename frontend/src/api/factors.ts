import { api } from 'src/api/http';

import type { AllSubmoduleTypes } from 'src/constant/modules';
import { enumSubmodule } from 'src/constant/modules';

export async function getSubclassMap(
  submodule: keyof typeof enumSubmodule,
  year: number | string,
): Promise<Record<string, string[]>> {
  const res = await api
    .get(
      `factors/${encodeURIComponent(enumSubmodule[submodule])}/class-subclass-map?year=${encodeURIComponent(String(year))}`,
    )
    .json<Record<string, string[]>>();
  return res ?? {};
}

export type ValueFactorResponse = Record<string, number | string | null> | null;

// ── Backoffice factor viewer (#1491) ──────────────────────────────────

export interface FactorsPaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// Handler response DTO dump plus year / last_seen_job_id — the concrete
// columns vary per data entry type, hence the open record.
export type BackofficeFactorRow = Record<string, unknown> & {
  id: number;
  year: number | null;
  last_seen_job_id: number | null;
};

export interface BackofficeFactorsResponse {
  data: BackofficeFactorRow[];
  pagination: FactorsPaginationMeta;
}

export async function listBackofficeFactors(params: {
  dataEntryTypeId: number;
  year: number;
  page: number;
  pageSize: number;
}): Promise<BackofficeFactorsResponse> {
  const searchParams = new URLSearchParams({
    data_entry_type_id: String(params.dataEntryTypeId),
    year: String(params.year),
    page: String(params.page),
    page_size: String(params.pageSize),
  });
  return await api
    .get('backoffice/factors', { searchParams })
    .json<BackofficeFactorsResponse>();
}

export async function getFactorValues(
  submodule: AllSubmoduleTypes,
  equipmentClass: string,
  subClass?: string | null,
  year?: string | number | null,
): Promise<ValueFactorResponse | null> {
  const params = new URLSearchParams();
  if (subClass) params.set('sub_class', subClass);
  if (year != null) params.set('year', String(year));
  const query = params.toString();
  const path =
    `factors/${encodeURIComponent(enumSubmodule[submodule])}/classes/${encodeURIComponent(equipmentClass)}/values` +
    (query ? `?${query}` : '');
  try {
    const res = await api
      .get(path, { skipErrorCodes: [404, 422] })
      .json<ValueFactorResponse | null>();
    return res ?? null;
  } catch (err) {
    console.error('Error fetching factor values:', err);
    return null;
  }
}
