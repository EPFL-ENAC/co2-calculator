import { api, SLOW_REQUEST_TIMEOUT_MS } from '@/api/http';

import type { AllSubmoduleTypes } from '@/constant/modules';
import { enumSubmodule } from '@/constant/modules';
import type { FactorRow } from '@/utils/factorOptions';

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

/**
 * The year's whole factor catalog for a submodule. Backs selects whose stored
 * value is an opaque classification code needing a human label (#2007).
 */
export async function listFactors(
  submodule: keyof typeof enumSubmodule,
  year: number | string,
): Promise<FactorRow[]> {
  const res = await api
    .get(
      `factors/${encodeURIComponent(enumSubmodule[submodule])}/list?year=${encodeURIComponent(String(year))}`,
      // Returns a whole year's factor catalog for the submodule, and the
      // largest of those measured 20,915 rows / 1338 ms server-side (#2049)
      // — under load it exceeded ky's 10 s default and the browser aborted
      // a request the backend was still answering (#2360).
      { timeout: SLOW_REQUEST_TIMEOUT_MS },
    )
    .json<FactorRow[]>();
  return res ?? [];
}

export type ValueFactorResponse = Record<string, number | string | null> | null;

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
