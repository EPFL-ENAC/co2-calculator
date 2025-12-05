import { api } from 'src/api/http';

export type SubmoduleKey = 'scientific' | 'it' | 'other';

export async function getClasses(submodule: SubmoduleKey): Promise<string[]> {
  const res = await api
    .get(`power-factors/${encodeURIComponent(submodule)}/classes`)
    .json<{ items: string[] }>();
  return Array.isArray(res.items) ? res.items : [];
}

export async function getSubclasses(
  submodule: SubmoduleKey,
  equipmentClass: string,
): Promise<string[]> {
  const res = await api
    .get(
      `power-factors/${encodeURIComponent(submodule)}/classes/${encodeURIComponent(
        equipmentClass,
      )}/subclasses`,
    )
    .json<{ items: string[] }>();
  return Array.isArray(res.items) ? res.items : [];
}

export interface PowerFactorResponse {
  submodule: string;
  equipment_class: string;
  sub_class: string | null;
  active_power_w: number;
  standby_power_w: number;
}

export async function getPowerFactor(
  submodule: SubmoduleKey,
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
