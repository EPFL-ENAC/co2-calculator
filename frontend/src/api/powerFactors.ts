import { api } from 'src/api/http';

import type { AllSubmoduleTypes } from 'src/constant/modules';
import { enumSubmodule } from 'src/constant/modules';

/** Recursive tree: keys are option values, leaves are empty objects. */
export interface OptionTree {
  [key: string]: OptionTree;
}

export async function getClassificationTree(
  submodule: AllSubmoduleTypes,
  unitId?: number,
): Promise<OptionTree> {
  const res = await api
    .get(
      `factors/${encodeURIComponent(enumSubmodule[submodule])}/classification-tree`,
      {
        searchParams: unitId ? { unit_id: unitId } : undefined,
      },
    )
    .json<OptionTree>();
  return res ?? {};
}

export interface PowerFactorResponse {
  active_power_w: number;
  standby_power_w: number;
}

export async function getPowerFactor(
  submodule: AllSubmoduleTypes,
  equipmentClass: string,
  subClass?: string | null,
): Promise<PowerFactorResponse | null> {
  let path = `factors/${encodeURIComponent(
    enumSubmodule[submodule],
  )}/classes/${encodeURIComponent(equipmentClass)}/power`;
  if (subClass) {
    path += `?sub_class=${encodeURIComponent(subClass)}`;
  }
  const res = await api.get(path).json<PowerFactorResponse | null>();
  return res ?? null;
}
