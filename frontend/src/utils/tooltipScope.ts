import type { Module } from 'src/constant/modules';

/**
 * The space a module is rendered in. The same module carries different guidance
 * depending on where it appears, so each space keys its own tooltip texts in
 * `src/i18n/tooltips.ts`.
 */
export type TooltipScope =
  'calculator' | 'planner-grant' | 'planner-year' | 'explorer';

const KEY_PREFIX: Record<TooltipScope, string> = {
  calculator: 'module',
  'planner-grant': 'planner-grant-module',
  'planner-year': 'planner-year-module',
  explorer: 'explorer-module',
};

export function moduleTooltipKey(scope: TooltipScope, module: Module): string {
  return `${KEY_PREFIX[scope]}-${module}-title`;
}

export function submoduleTooltipKey(
  scope: TooltipScope,
  module: Module,
  submodule: string,
): string {
  return `${KEY_PREFIX[scope]}-${module}-submodule-${submodule}`;
}
