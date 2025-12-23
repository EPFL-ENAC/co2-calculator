import { api } from 'src/api/http';

import type { AllSubmoduleTypes } from 'src/constant/modules';

export async function getSubclassMap(
  submodule: AllSubmoduleTypes,
): Promise<Record<string, string[]>> {
  const res = await api
    .get(`power-factors/${encodeURIComponent(submodule)}/class-subclass-map`)
    .json<{ items: Record<string, string[]> }>();
  return res.items ?? {};
}

export interface PowerFactorResponse {
  submodule: string;
  equipment_class: string;
  sub_class: string | null;
  active_power_w: number;
  standby_power_w: number;
}

export async function getPowerFactor(
  submodule: AllSubmoduleTypes,
  equipmentClass: string,
  subClass?: string | null,
): Promise<PowerFactorResponse | null> {
  let path = `power-factors/${encodeURIComponent(
    submodule,
  )}/classes/${encodeURIComponent(equipmentClass)}/power`;
  if (subClass) {
    path += `?sub_class=${encodeURIComponent(subClass)}`;
  }
  const res = await api.get(path).json<PowerFactorResponse | null>();
  return res ?? null;
}
