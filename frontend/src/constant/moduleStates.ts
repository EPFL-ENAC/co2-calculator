import type { Module } from './modules';

export const MODULE_STATES = {
  Default: 'default',
  InProgress: 'in-progress',
  Validated: 'validated',
} as const;

export type ModuleState = (typeof MODULE_STATES)[keyof typeof MODULE_STATES];
export type ModuleStates = { [K in Module]: ModuleState };
