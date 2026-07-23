<template>
  <q-card flat bordered>
    <q-expansion-item
      v-model="yearOpen"
      header-class="text-h5 text-weight-bold"
    >
      <template #header>
        <q-item-section>{{ yearData.year }}</q-item-section>
      </template>

      <q-separator />
      <q-card-section>
        <div class="text-weight-bold q-mb-sm">
          {{ $t('planner_reference_year_label') }}
        </div>
        <!-- Set: the value reads first, the action stays quiet beside it.
             Unset: nothing to read yet, so the action carries the label. -->
        <div
          v-if="yearData.reference_year"
          class="reference-year-row row items-center no-wrap"
        >
          <q-icon
            name="o_calendar_month"
            color="info"
            class="reference-year-row__icon"
          />
          <span class="reference-year-row__value text-weight-bold">
            {{ yearData.reference_year }}
          </span>
          <q-separator vertical class="reference-year-row__divider" />
          <q-btn
            :label="$t('planner_reference_year_change_link')"
            color="info"
            flat
            dense
            no-caps
            padding="none"
            class="reference-year-row__action text-weight-medium"
            :loading="settingReferenceYear"
            @click="referenceYearDialogOpen = true"
          />
        </div>
        <q-btn
          v-else
          color="info"
          flat
          no-caps
          align="left"
          class="reference-year-empty text-weight-medium"
          :loading="settingReferenceYear"
          @click="referenceYearDialogOpen = true"
        >
          <q-icon name="o_calendar_month" class="reference-year-row__icon" />
          <span>{{ $t('planner_reference_year_set_button') }}</span>
        </q-btn>
        <div class="text-body2 text-grey-7 q-mt-xs">
          {{
            yearData.reference_year
              ? $t('planner_reference_year_rebuild_hint')
              : $t('planner_reference_year_hint')
          }}
        </div>
      </q-card-section>

      <planner-reference-year-dialog
        v-if="referenceYearDialogOpen"
        :key="`ref-year-${yearData.reference_year}`"
        v-model="referenceYearDialogOpen"
        :year="yearData.year"
        :reference-year="yearData.reference_year"
        :options="referenceYearOptions"
        :loading="settingReferenceYear"
        @confirm="onReferenceYearChange"
      />

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
            :disable="!hasReferenceYear"
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
                  <q-checkbox
                    :model-value="entry.module?.is_active ?? true"
                    :label="$t('planner_module_active_label')"
                    color="negative"
                    :disable="
                      !entry.module || togglingModuleId === entry.module.id
                    "
                    @update:model-value="
                      (active: boolean) => onToggleActive(entry, active)
                    "
                  >
                    <q-tooltip>{{
                      $t('planner_module_active_tooltip')
                    }}</q-tooltip>
                  </q-checkbox>
                </div>
              </q-item-section>
            </template>

            <q-separator />
            <div
              v-if="expandedKey === expansionKey(entry.config.module)"
              class="q-pa-md"
            >
              <!-- Headcount is a fixed SIUS-category grid, not an add-row
                   table (design). Other modules reuse the Calculator tables. -->
              <planner-headcount-rows
                v-if="entry.config.module === MODULES.Headcount"
                :carbon-report-id="yearData.id"
                :disable="entry.module?.is_active === false"
              />
              <module-table-section
                v-else
                :key="factorScopedKey(entry.config.module)"
                :type="entry.config.module"
                :config-override="getPlannerModuleConfig(entry.config.module)"
                :data="moduleStore.state.data"
                :loading="moduleStore.state.loading"
                :error="moduleStore.state.error"
                :unit-id="unitId"
                :year="yearData.year"
                :factor-year="yearData.reference_year"
                :carbon-report-id="yearData.id"
                :show-reference-columns="entry.config.behavior === 'prefilled'"
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
import PlannerHeadcountRows from 'src/components/organisms/planner/PlannerHeadcountRows.vue';
import PlannerReferenceYearDialog from 'src/components/organisms/planner/PlannerReferenceYearDialog.vue';
import {
  PLANNER_MODULES,
  type PlannerModuleConfig,
} from 'src/constant/planner-module-config';
import { getPlannerModuleConfig } from 'src/constant/planner-module-config/module-configs';
import { getModuleTypeId } from 'src/constant/moduleStates';
import { MODULES, type Module } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { factorMountKey } from 'src/utils/factor-year';
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
const referenceYearDialogOpen = ref(false);
const togglingModuleId = ref<number | null>(null);

// Every module resolves its factors from the reference year; without one there
// is nothing to enter data against, so the drawers stay shut.
const hasReferenceYear = computed(() => props.yearData.reference_year !== null);

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

function factorScopedKey(module: Module): string {
  return factorMountKey(module, props.yearData.reference_year);
}

async function refreshExpandedModule(module: Module) {
  await moduleStore.getModuleTotals(
    module,
    props.unitId,
    String(props.yearData.year),
    props.yearData.id,
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
    referenceYearDialogOpen.value = false;
    // The new baseline's rows are prefilled (or restored); refresh the open
    // module so they appear without a manual reload.
    const expanded = props.expandedKey?.startsWith(`${props.yearData.year}-`);
    const module = props.expandedKey?.split('-').slice(1).join('-') as
      Module | undefined;
    if (expanded && module) await refreshExpandedModule(module);
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
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

// Setting row: the current value reads as the content, the action sits quietly
// beside it — changing the baseline is deliberate, not a stray click.
.reference-year-row {
  display: inline-flex;
  gap: tokens.$reference-year-row-gap;
  padding: tokens.$reference-year-row-padding-y
    tokens.$reference-year-row-padding-x;
  border: tokens.$reference-year-row-border-weight solid
    tokens.$reference-year-row-border-color;
  border-radius: tokens.$reference-year-row-border-radius;

  &__icon {
    font-size: tokens.$reference-year-row-icon-size;
  }

  &__value {
    font-size: tokens.$reference-year-row-value-font-size;
    line-height: 1;
  }

  &__divider {
    height: tokens.$reference-year-row-divider-height;
    align-self: center;
  }

  &__action {
    font-size: tokens.$reference-year-row-action-font-size;
  }
}

// The same slot before it holds anything: dashed, so it reads as waiting to be
// filled rather than as a call to action competing with the module list.
.reference-year-empty {
  padding: tokens.$reference-year-row-padding-y
    tokens.$reference-year-row-padding-x;
  border: tokens.$reference-year-row-border-weight
    tokens.$reference-year-row-empty-border-style
    tokens.$reference-year-row-empty-border-color;
  border-radius: tokens.$reference-year-row-border-radius;
  font-size: tokens.$reference-year-row-value-font-size;

  :deep(.q-btn__content) {
    gap: tokens.$reference-year-row-gap;
  }
}
</style>
