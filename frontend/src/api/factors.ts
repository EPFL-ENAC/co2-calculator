import { api } from 'src/api/http';

import type { AllSubmoduleTypes } from 'src/constant/modules';
import { enumSubmodule } from 'src/constant/modules';
import type { FactorRow } from 'src/utils/factorOptions';

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
