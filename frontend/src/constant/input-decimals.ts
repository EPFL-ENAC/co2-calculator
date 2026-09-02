import { getBackendModuleName, type Module } from '@/constant/modules';
import {
  DEFAULT_INPUT_DECIMALS,
  MODULE_INPUT_DECIMALS,
} from '@/types/module-lookups.gen';

export function moduleInputDecimals(module: Module): number {
  return (
    MODULE_INPUT_DECIMALS[getBackendModuleName(module)] ??
    DEFAULT_INPUT_DECIMALS
  );
}

export function moduleInputStep(module: Module): number {
  return 10 ** -moduleInputDecimals(module);
}

export function roundModuleInput(module: Module, value: number): number {
  const factor = 10 ** moduleInputDecimals(module);
  return Math.round(value * factor) / factor;
}
