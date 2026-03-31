<script setup lang="ts">
import { ref, watch } from 'vue';
import { MODULES_LIST, type Module } from 'src/constant/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import ModuleConfigItem from './ModuleConfigItem.vue';

interface Props {
  year: number;
}

const props = defineProps<Props>();
const { t: $t } = useI18n();
const yearConfigStore = useYearConfigStore();

const expandedModules = ref<Record<string, boolean>>({});
const localConfig = ref<Record<string, Record<string, unknown>>>({});

// Fetch configuration on mount and year change
const loadConfig = async () => {
  try {
    const response = await yearConfigStore.fetchConfig(props.year);
    // Initialize local config from API response
    MODULES_LIST.forEach((module) => {
      const moduleTypeId = getModuleTypeId(module);
      const moduleConfig = response.config.modules[moduleTypeId.toString()];
      if (moduleConfig) {
        localConfig.value[module] = {
          enabled: moduleConfig.enabled,
          uncertainty_tag: moduleConfig.uncertainty_tag,
          submodules: moduleConfig.submodules,
        };
      } else {
        // Default config if not found
        localConfig.value[module] = {
          enabled: true,
          uncertainty_tag: 'medium' as const,
          submodules: {},
        };
      }
    });
  } catch (err) {
    console.error('Failed to load year configuration:', err);
    Notify.create({
      type: 'negative',
      message: $t('year_config_load_error'),
    });
  }
};

// Save configuration
const saveConfig = async (module: Module, updates: Record<string, unknown>) => {
  const moduleTypeId = getModuleTypeId(module);

  try {
    await yearConfigStore.updateConfig(props.year, {
      config: {
        modules: {
          [moduleTypeId.toString()]: {
            ...localConfig.value[module],
            ...updates,
          },
        },
      },
    });

    Notify.create({
      type: 'positive',
      message: $t('year_config_saved'),
    });
  } catch (err) {
    console.error('Failed to save configuration:', err);
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  }
};

watch(
  () => props.year,
  () => {
    loadConfig();
  },
  { immediate: true },
);

// Helper to get module type ID
const getModuleTypeId = (module: Module): number => {
  const moduleMap: Record<Module, number> = {
    headcount: 1,
    'professional-travel': 2,
    buildings: 3,
    'equipment-electric-consumption': 4,
    purchase: 5,
    'research-facilities': 6,
    'external-cloud-and-ai': 7,
    'process-emissions': 8,
  };
  return moduleMap[module] || 0;
};
</script>

<template>
  <div>
    <div class="text-h5 q-mb-md">{{ $t('module_configuration') }}</div>

    <template v-for="module in MODULES_LIST" :key="module">
      <module-config-item
        v-model:config="localConfig[module]"
        :year="year"
        :module="module"
        :expanded="expandedModules[module]"
        class="q-mb-md"
        @update:expanded="expandedModules[module] = $event"
        @save="saveConfig(module, $event)"
      />
    </template>
  </div>
</template>
