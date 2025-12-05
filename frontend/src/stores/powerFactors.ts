import { defineStore } from 'pinia';
import { getClasses, getSubclasses, SubmoduleKey } from 'src/api/powerFactors';

type Option = { label: string; value: string };

export const usePowerFactorsStore = defineStore('power-factors', () => {
  async function fetchClassOptions(submodule: SubmoduleKey): Promise<Option[]> {
    const classes = await getClasses(submodule);
    return classes.map((c) => ({ label: c, value: c }));
  }

  async function fetchSubclassOptions(
    submodule: SubmoduleKey,
    equipmentClass: string,
  ): Promise<Option[]> {
    const subclasses = await getSubclasses(submodule, equipmentClass);
    return subclasses.map((s) => ({ label: s, value: s }));
  }

  return {
    fetchClassOptions,
    fetchSubclassOptions,
  };
});
