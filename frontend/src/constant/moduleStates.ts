import type { Module } from './modules';

export const MODULE_STATES = ['default', 'in-progress', 'validated'] as const;

export type ModuleState = (typeof MODULE_STATES)[number];
export type ModuleStates = { [K in Module]: ModuleState };
