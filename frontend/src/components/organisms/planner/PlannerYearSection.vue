<template>
  <q-card flat bordered class="q-pa-lg">
    <div class="row items-center q-col-gutter-md q-mb-md">
      <h2 class="text-h4 q-my-none col">
        {{ $t('planner_year_section_title', { year: yearData.year }) }}
      </h2>
      <q-select
        :model-value="yearData.reference_year"
        :options="referenceYearOptions"
        :label="$t('planner_reference_year_label')"
        outlined
        dense
        emit-value
        map-options
        class="col-12 col-md-3"
        :loading="settingReferenceYear"
        @update:model-value="onReferenceYearChange"
      />
    </div>
    <p v-if="!yearData.reference_year" class="text-body2 text-grey-8">
      {{ $t('planner_reference_year_hint') }}
    </p>

    <q-list separator>
      <q-expansion-item
        v-for="entry in moduleEntries"
        :key="entry.config.module"
        :model-value="expandedKey === expansionKey(entry.config.module)"
        @update:model-value="
          (open: boolean) => onToggle(entry.config.module, open)
        "
      >
        <template #header>
          <q-item-section side @click.stop>
            <q-checkbox
              :model-value="entry.module?.is_active ?? true"
              :disable="!entry.module || togglingModuleId === entry.module.id"
              @update:model-value="
                (active: boolean) => onToggleActive(entry, active)
              "
            >
              <q-tooltip>{{ $t('planner_module_active_tooltip') }}</q-tooltip>
            </q-checkbox>
          </q-item-section>
          <q-item-section>
            <div class="row items-center q-gutter-sm">
              <span class="text-weight-medium">
                {{ $t(`module-${entry.config.module}-title`) }}
              </span>
              <q-badge
                v-if="entry.config.behavior === 'prefilled'"
                outline
                color="info"
                :label="$t('planner_module_prefilled_badge')"
              />
            </div>
          </q-item-section>
          <q-item-section side @click.stop>
            <q-btn
              v-if="entry.config.behavior === 'prefilled'"
              unelevated
              no-caps
              dense
              size="sm"
              color="info"
              :label="$t('planner_module_prefill_button')"
              :disable="!yearData.reference_year || !entry.module"
              :loading="prefillingModule === entry.config.module"
              @click="onPrefill(entry.config.module)"
            >
              <q-tooltip v-if="!yearData.reference_year">
                {{ $t('planner_reference_year_hint') }}
              </q-tooltip>
            </q-btn>
          </q-item-section>
        </template>

        <div
          v-if="expandedKey === expansionKey(entry.config.module)"
          class="q-pa-md"
        >
          <module-table-section
            :type="entry.config.module"
            :config-override="getPlannerModuleConfig(entry.config.module)"
            :data="moduleStore.state.data"
            :loading="moduleStore.state.loading"
            :error="moduleStore.state.error"
            :unit-id="unitId"
            :year="yearData.year"
            :disable="entry.module?.is_active === false"
          />
        </div>
      </q-expansion-item>
    </q-list>
  </q-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

import ModuleTableSection from 'src/components/organisms/module/ModuleTableSection.vue';
import {
  PLANNER_MODULES,
  type PlannerModuleConfig,
} from 'src/constant/planner-module-config';
import { getPlannerModuleConfig } from 'src/constant/planner-module-config/module-configs';
import { getModuleTypeId } from 'src/constant/moduleStates';
import type { Module } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import {
  useSimulatorPlansStore,
  type SimulatorPlanModule,
  type SimulatorPlanYear,
} from 'src/stores/simulatorPlans';

interface ModuleEntry {
  config: PlannerModuleConfig;
  module: SimulatorPlanModule | undefined;
}

const props = defineProps<{
  planId: number;
  yearData: SimulatorPlanYear;
  unitId: number;
  referenceYearOptions: { label: string; value: number }[];
  /** `${year}-${module}` of the single expanded module across the page. */
  expandedKey: string | null;
}>();
const emit = defineEmits<{ 'update:expandedKey': [key: string | null] }>();

const $q = useQuasar();
const { t } = useI18n();
const moduleStore = useModuleStore();
const plansStore = useSimulatorPlansStore();

const settingReferenceYear = ref(false);
const prefillingModule = ref<Module | null>(null);
const togglingModuleId = ref<number | null>(null);

const moduleEntries = computed<ModuleEntry[]>(() =>
  PLANNER_MODULES.map((config) => ({
    config,
    module: props.yearData.modules.find(
      (m) => m.module_type_id === getModuleTypeId(config.module),
    ),
  })),
);

function expansionKey(module: Module): string {
  return `${props.yearData.year}-${module}`;
}

async function refreshExpandedModule(module: Module) {
  await moduleStore.getModuleTotals(
    module,
    props.unitId,
    String(props.yearData.year),
  );
}

function onToggle(module: Module, open: boolean) {
  emit('update:expandedKey', open ? expansionKey(module) : null);
  if (open) void refreshExpandedModule(module);
}

async function onReferenceYearChange(referenceYear: number) {
  settingReferenceYear.value = true;
  try {
    await plansStore.setReferenceYear(
      props.planId,
      props.yearData.year,
      referenceYear,
    );
  } catch {
    $q.notify({ type: 'negative', message: t('planner_reference_year_error') });
  } finally {
    settingReferenceYear.value = false;
  }
}

async function onToggleActive(entry: ModuleEntry, active: boolean) {
  if (!entry.module) return;
  togglingModuleId.value = entry.module.id;
  try {
    await plansStore.setModuleActive(
      props.yearData.id,
      entry.module.module_type_id,
      active,
    );
  } finally {
    togglingModuleId.value = null;
  }
}

async function onPrefill(module: Module) {
  prefillingModule.value = module;
  try {
    await plansStore.prefillModule(props.yearData.id, module);
    if (props.expandedKey === expansionKey(module)) {
      await refreshExpandedModule(module);
    }
    $q.notify({ type: 'positive', message: t('planner_prefill_done') });
  } catch {
    $q.notify({ type: 'negative', message: t('planner_prefill_error') });
  } finally {
    prefillingModule.value = null;
  }
}
</script>
