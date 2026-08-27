import { api } from '@/api/http';

import type { AllSubmoduleTypes } from '@/constant/modules';
import { enumSubmodule } from '@/constant/modules';

export type ValueFactorResponse = Record<string, number | string | null> | null;

/**
 * The one factor route the frontend still calls: the equipment form/table
 * prefill for a single picked class (#2391 decision 3). Options themselves
 * come from the taxonomy endpoint — see `api/taxonomies.ts`.
 */
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
