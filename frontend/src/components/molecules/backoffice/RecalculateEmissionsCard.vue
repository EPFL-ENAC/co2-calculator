<template>
  <q-card flat bordered class="q-mb-lg">
    <q-card-section class="row items-center q-py-sm">
      <div class="text-subtitle2 q-mr-md">
        {{ $t('pipeops_recalc_title') }}
      </div>
      <q-space />
      <q-select
        :model-value="moduleTypeId"
        dense
        outlined
        emit-value
        map-options
        :placeholder="$t('pipeops_recompute_module_type_placeholder')"
        :options="moduleTypeOptions"
        style="width: 220px"
        class="q-mr-sm"
        data-testid="recalc-module"
        @update:model-value="onModuleChange"
      />
      <q-select
        v-model="dataEntryTypeId"
        dense
        outlined
        clearable
        emit-value
        map-options
        :disable="moduleTypeId === null"
        :placeholder="$t('pipeops_recalc_data_entry_type_placeholder')"
        :options="dataEntryTypeOptions"
        style="width: 200px"
        class="q-mr-sm"
        data-testid="recalc-type"
      />
      <q-select
        v-model="year"
        dense
        outlined
        :placeholder="$t('pipeops_recompute_year_placeholder')"
        :options="yearOptions"
        style="width: 140px"
        class="q-mr-sm"
        data-testid="recalc-year"
      />
      <q-btn
        color="primary"
        no-caps
        :label="$t('pipeops_recalc_trigger')"
        :disable="moduleTypeId === null || year === null"
        data-testid="recalc-trigger"
        @click="confirmDialog = true"
      />
    </q-card-section>
    <q-card-section class="text-caption text-grey-7 q-pt-none">
      {{ $t('pipeops_recalc_hint') }}
    </q-card-section>
  </q-card>

  <q-dialog v-model="confirmDialog" persistent>
    <q-card style="max-width: 520px">
      <q-card-section class="text-h6">
        {{ $t('data_management_recalculate_emissions_title') }}
      </q-card-section>
      <q-card-section class="q-pt-none">
        <div class="text-weight-medium q-mb-sm">
          {{ moduleTypeLabel }} · {{ dataEntryTypeLabel }} · {{ year }}
        </div>
        {{ $t('data_management_recalculate_emissions_description') }}
      </q-card-section>
      <q-card-actions align="right">
        <q-btn
          flat
          no-caps
          :label="$t('common_cancel')"
          @click="confirmDialog = false"
        />
        <q-btn
          color="primary"
          no-caps
          :label="$t('pipeops_recalc_trigger')"
          :loading="triggering"
          data-testid="recalc-confirm"
          @click="onConfirm"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Notify } from 'quasar';
import { HTTPError } from 'ky';
import { useI18n } from 'vue-i18n';
import { useBackofficeDataManagement } from '@/stores/backofficeDataManagement';
import { useYearConfigStore } from '@/stores/yearConfig';
import {
  MODULE_SUBMODULES,
  type SubmoduleConfig,
} from '@/constant/backoffice-module-config';

const emit = defineEmits<{ (e: 'triggered'): void }>();

const { t } = useI18n();
const store = useBackofficeDataManagement();
const yearConfigStore = useYearConfigStore();

const moduleTypeId = ref<number | null>(null);
const dataEntryTypeId = ref<number | null>(null);
const year = ref<number | null>(null);
const confirmDialog = ref(false);
const triggering = ref(false);

// Same year source as RecomputeStatsCard: only configured years.
const yearOptions = computed(() =>
  [...yearConfigStore.configuredYears].map((y) => y.year).sort((a, b) => b - a),
);

onMounted(() => {
  if (yearConfigStore.configuredYears.length === 0) {
    void yearConfigStore.fetchConfiguredYears();
  }
});

const submodules = Object.entries(MODULE_SUBMODULES).flatMap(
  ([moduleKey, subs]) =>
    (subs ?? []).map((sub: SubmoduleConfig) => ({ moduleKey, sub })),
);

const moduleTypeOptions = computed(() => {
  const byId = new Map<number, string>();
  for (const { moduleKey, sub } of submodules) {
    if (!byId.has(sub.moduleTypeId)) byId.set(sub.moduleTypeId, t(moduleKey));
  }
  return [...byId]
    .map(([value, label]) => ({ label, value }))
    .sort((a, b) => a.value - b.value);
});

const dataEntryTypeOptions = computed(() =>
  submodules
    .filter(
      ({ sub }) =>
        sub.moduleTypeId === moduleTypeId.value &&
        sub.dataEntryTypeId !== undefined,
    )
    .map(({ sub }) => ({ label: t(sub.labelKey), value: sub.dataEntryTypeId })),
);

const moduleTypeLabel = computed(
  () =>
    moduleTypeOptions.value.find((o) => o.value === moduleTypeId.value)?.label,
);

const dataEntryTypeLabel = computed(
  () =>
    dataEntryTypeOptions.value.find((o) => o.value === dataEntryTypeId.value)
      ?.label ?? t('pipeops_recalc_all_types'),
);

function onModuleChange(value: number): void {
  moduleTypeId.value = value;
  dataEntryTypeId.value = null;
}

async function onConfirm(): Promise<void> {
  const moduleType = moduleTypeId.value;
  const targetYear = year.value;
  if (moduleType === null || targetYear === null) return;
  triggering.value = true;
  try {
    // Module path: only_stale=false, the operator asked for a full recalc.
    if (dataEntryTypeId.value === null) {
      await store.initiateModuleEmissionRecalculation(
        moduleType,
        targetYear,
        false,
      );
    } else {
      await store.initiateEmissionRecalculation(
        moduleType,
        dataEntryTypeId.value,
        targetYear,
      );
    }
    Notify.create({ type: 'positive', message: t('pipeops_recalc_success') });
    confirmDialog.value = false;
    emit('triggered');
  } catch (err: unknown) {
    // The api client already toasts the backend's detail for HTTP errors.
    if (err instanceof HTTPError) return;
    Notify.create({ type: 'negative', message: t('pipeops_recalc_failed') });
  } finally {
    triggering.value = false;
  }
}
</script>
