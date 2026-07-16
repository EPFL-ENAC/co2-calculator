<template>
  <q-card flat bordered>
    <q-expansion-item v-model="yearOpen" header-class="text-h5 text-weight-bold">
      <template #header>
        <q-item-section>{{ yearData.year }}</q-item-section>
      </template>

      <q-separator />
      <q-card-section>
        <div class="text-weight-bold q-mb-sm">
          {{ $t('planner_reference_year_label') }}
        </div>
        <q-select
          :model-value="yearData.reference_year"
          :options="referenceYearOptions"
          outlined
          dense
          emit-value
          map-options
          class="planner-reference-year"
          :loading="settingReferenceYear"
          @update:model-value="onReferenceYearChange"
        >
          <template #prepend>
            <q-icon name="o_calendar_month" color="negative" />
          </template>
        </q-select>
        <div v-if="!yearData.reference_year" class="text-body2 text-grey-7 q-mt-sm">
          {{ $t('planner_reference_year_hint') }}
        </div>
      </q-card-section>

      <!-- One bordered card per module, in Calculator order -->
      <q-card-section class="q-gutter-md">
        <q-card
          v-for="entry in moduleEntries"
          :key="entry.config.module"
          flat
          bordered
        >
          <q-expansion-item
            :model-value="expandedKey === expansionKey(entry.config.module)"
            @update:model-value="
              (open: boolean) => onToggle(entry.config.module, open)
            "
          >
            <template #header>
              <q-item-section avatar>
                <module-icon-box :name="entry.config.module" size="md" />
              </q-item-section>
              <q-item-section class="text-weight-medium">
                {{ $t(entry.config.module) }}
              </q-item-section>
              <q-item-section side @click.stop>
                <div class="row items-center no-wrap q-gutter-sm">
                  <q-btn
                    v-if="entry.config.behavior === 'prefilled'"
                    unelevated
                    no-caps
                    dense
                    size="sm"
                    color="negative"
                    :label="$t('planner_module_prefill_button')"
                    :disable="!yearData.reference_year || !entry.module"
                    :loading="prefillingModule === entry.config.module"
                    @click="onPrefill(entry.config.module)"
                  >
                    <q-tooltip v-if="!yearData.reference_year">
                      {{ $t('planner_reference_year_hint') }}
                    </q-tooltip>
                  </q-btn>
                  <q-checkbox
                    :model-value="entry.module?.is_active ?? true"
                    :label="$t('planner_module_active_label')"
                    color="negative"
                    :disable="!entry.module || togglingModuleId === entry.module.id"
                    @update:model-value="
                      (active: boolean) => onToggleActive(entry, active)
                    "
                  >
                    <q-tooltip>{{ $t('planner_module_active_tooltip') }}</q-tooltip>
                  </q-checkbox>
                </div>
              </q-item-section>
            </template>

            <q-separator />
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
        </q-card>
      </q-card-section>
    </q-expansion-item>
  </q-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';
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

const yearOpen = ref(true);
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

<style scoped lang="scss">
.planner-reference-year {
  max-width: 320px;
}
</style>
