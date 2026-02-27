import { api } from 'src/api/http';

import type { AllSubmoduleTypes } from 'src/constant/modules';
import { enumSubmodule } from 'src/constant/modules';

export async function getSubclassMap(
  submodule: keyof typeof enumSubmodule,
  unitId?: number,
): Promise<Record<string, string[]>> {
  const res = await api
    .get(
      `factors/${encodeURIComponent(enumSubmodule[submodule])}/class-subclass-map`,
      {
        searchParams: unitId ? { unit_id: unitId } : undefined,
      },
    )
    .json<Record<string, string[]>>();
  return res ?? {};
}

export type ValueFactorResponse = Record<string, number> | null;

export async function getFactorValues(
  submodule: AllSubmoduleTypes,
  equipmentClass: string,
  subClass?: string | null,
): Promise<ValueFactorResponse | null> {
  let path = `factors/${encodeURIComponent(
    enumSubmodule[submodule],
  )}/classes/${encodeURIComponent(equipmentClass)}/power`;
  if (subClass) {
    path += `?sub_class=${encodeURIComponent(subClass)}`;
  }
  const res = await api.get(path).json<ValueFactorResponse | null>();
  return res ?? null;
}
