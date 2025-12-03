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
