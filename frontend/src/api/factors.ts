import { api } from 'src/api/http';

import type { AllSubmoduleTypes } from 'src/constant/modules';
import { enumSubmodule } from 'src/constant/modules';

export async function getSubclassMap(
  submodule: keyof typeof enumSubmodule,
): Promise<Record<string, string[]>> {
  const res = await api
    .get(
      `factors/${encodeURIComponent(enumSubmodule[submodule])}/class-subclass-map`,
    )
    .json<Record<string, string[]>>();
  return res ?? {};
}

export type ValueFactorResponse = Record<string, number | string | null> | null;

export async function getFactorValues(
  submodule: AllSubmoduleTypes,
  equipmentClass: string,
  subClass?: string | null,
): Promise<ValueFactorResponse | null> {
  let path = `factors/${encodeURIComponent(
    enumSubmodule[submodule],
  )}/classes/${encodeURIComponent(equipmentClass)}/values`;
  if (subClass) {
    path += `?sub_class=${encodeURIComponent(subClass)}`;
  }
  const res = await api.get(path).json<ValueFactorResponse | null>();
  return res ?? null;
}
