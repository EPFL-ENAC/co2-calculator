<template>
  <q-card flat bordered class="q-mb-lg">
    <q-card-section class="row items-center q-py-sm">
      <div class="text-subtitle2 q-mr-md">
        {{ $t('pipeops_recompute_title') }}
      </div>
      <q-space />
      <q-select
        v-model="moduleTypeId"
        dense
        outlined
        clearable
        emit-value
        map-options
        :placeholder="$t('pipeops_recompute_module_type_placeholder')"
        :options="moduleTypeOptions"
        style="width: 220px"
        class="q-mr-sm"
      />
      <q-select
        v-model="year"
        dense
        outlined
        clearable
        :placeholder="$t('pipeops_recompute_year_placeholder')"
        :options="yearOptions"
        style="width: 140px"
        class="q-mr-sm"
      />
      <q-btn
        color="primary"
        no-caps
        :label="$t('pipeops_recompute_trigger')"
        @click="confirmDialog = true"
      />
    </q-card-section>
    <q-card-section class="text-caption text-grey-7 q-pt-none">
      {{ $t('pipeops_recompute_hint') }}
    </q-card-section>
  </q-card>

  <q-dialog v-model="confirmDialog" persistent>
    <q-card style="min-width: 420px">
      <q-card-section class="text-h6">
        {{ $t('pipeops_recompute_title') }}
      </q-card-section>
      <q-card-section class="q-pt-none">
        {{
          year && moduleTypeLabel
            ? $t('pipeops_recompute_confirm_year_module', {
                year,
                moduleType: moduleTypeLabel,
              })
            : year
              ? $t('pipeops_recompute_confirm_year', { year })
              : moduleTypeLabel
                ? $t('pipeops_recompute_confirm_all_module', {
                    moduleType: moduleTypeLabel,
                  })
                : $t('pipeops_recompute_confirm_all')
        }}
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat no-caps :label="$t('common_cancel')" />
        <q-btn
          color="primary"
          no-caps
          :label="$t('pipeops_recompute_trigger')"
          :loading="triggering"
          @click="onConfirm"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useBackofficeDataManagement } from '@/stores/backofficeDataManagement';
import { useYearConfigStore } from '@/stores/yearConfig';
import { MODULE_SUBMODULES } from '@/constant/backoffice-module-config';

const { t } = useI18n();
const store = useBackofficeDataManagement();
const yearConfigStore = useYearConfigStore();

const year = ref<number | null>(null);
const moduleTypeId = ref<number | null>(null);
const confirmDialog = ref(false);
const triggering = ref(false);

// Only years that actually have a year-configuration row are valid
// recompute targets — an arbitrary typed year could silently no-op
// (list_module_type_year_scopes returns nothing for a year nobody
// configured) with no feedback as to why.
const yearOptions = computed(() =>
  [...yearConfigStore.configuredYears].map((y) => y.year).sort((a, b) => b - a),
);

onMounted(() => {
  if (yearConfigStore.configuredYears.length === 0) {
    void yearConfigStore.fetchConfiguredYears();
  }
});

// One option per distinct moduleTypeId, first submodule's parent module
// used for the label — the submodule split (e.g. headcount member/student)
// doesn't matter for a recompute scope, which is per module type only.
const moduleTypeOptions = computed(() => {
  const seen = new Set<number>();
  const options: { label: string; value: number }[] = [];
  for (const [moduleKey, submodules] of Object.entries(MODULE_SUBMODULES)) {
    const id = submodules?.[0]?.moduleTypeId;
    if (id == null || seen.has(id)) continue;
    seen.add(id);
    options.push({ label: t(moduleKey), value: id });
  }
  return options.sort((a, b) => a.value - b.value);
});

const moduleTypeLabel = computed(
  () =>
    moduleTypeOptions.value.find((o) => o.value === moduleTypeId.value)
      ?.label ?? null,
);

async function onConfirm(): Promise<void> {
  triggering.value = true;
  try {
    const result = await store.recomputeStats(year.value, moduleTypeId.value);
    Notify.create({
      type: 'positive',
      message:
        result.skipped_no_factors > 0
          ? t('pipeops_recompute_success_no_factors', {
              dispatched: result.dispatched,
              skipped: result.skipped,
              skippedNoFactors: result.skipped_no_factors,
            })
          : t('pipeops_recompute_success', {
              dispatched: result.dispatched,
              skipped: result.skipped,
            }),
      timeout: 3000,
    });
    confirmDialog.value = false;
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : t('pipeops_recompute_failed');
    Notify.create({ type: 'negative', message: msg });
  } finally {
    triggering.value = false;
  }
}
</script>
