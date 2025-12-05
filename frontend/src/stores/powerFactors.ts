import { defineStore } from 'pinia';
import {
  getClasses,
  getSubclasses,
  getPowerFactor,
  SubmoduleKey,
  PowerFactorResponse,
} from 'src/api/powerFactors';

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

  async function fetchPowerFactor(
    submodule: SubmoduleKey,
    equipmentClass: string,
    subClass?: string | null,
  ): Promise<PowerFactorResponse | null> {
    return await getPowerFactor(submodule, equipmentClass, subClass);
  }

  return {
    fetchClassOptions,
    fetchSubclassOptions,
    fetchPowerFactor,
  };
});
