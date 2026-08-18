import { MODULES_CONFIG } from 'src/constant/module-config';
import type { ModuleConfig, Submodule } from 'src/constant/moduleConfig';
import type { Module } from 'src/constant/modules';
import { MODULES_ORDER } from 'src/constant/timelineItems';
import type { UnifiedModuleConfig } from 'src/stores/yearConfig';

export interface ExploreModule {
  type: Module;
  config: ModuleConfig;
  submodules: Submodule[];
}

export function getExploreModules(
  getModule: (type: Module) => UnifiedModuleConfig | null,
): ExploreModule[] {
  return MODULES_ORDER.map((type): ExploreModule | null => {
    const config = MODULES_CONFIG[type] as ModuleConfig | undefined;
    if (!config?.submodules?.length) return null;

    const unifiedConfig = getModule(type);
    const visibleSubmodules = unifiedConfig
      ? config.submodules.filter(
          (sub) => unifiedConfig.submodules[sub.id]?.enabled ?? true,
        )
      : config.submodules;

    if (!visibleSubmodules.length) return null;

    return {
      type,
      config,
      submodules: visibleSubmodules,
    };
  }).filter((m): m is ExploreModule => m !== null);
}
