<script setup lang="ts">
import { computed, ref, watch, onMounted, provide } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import { MODULES_LIST } from 'src/constant/modules';

import ModuleConfig from 'src/components/organisms/data-management/ModuleConfig.vue';
import ReductionObjectivesSection from 'src/components/organisms/data-management/ReductionObjectivesSection.vue';
import DataEntryDialog from 'src/components/organisms/data-management/DataEntryDialog.vue';

import {
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { usePipelineStream } from 'src/composables/usePipelineStream';
import { Notify, Loading } from 'quasar';
import { useI18n } from 'vue-i18n';

// TODO: fix the available years dynamically
const route = useRoute();
const router = useRouter();
const MIN_YEARS = 2024;
const availableYears = ref<number[]>([]);
const currentYear = new Date().getFullYear();
if (currentYear > MIN_YEARS) {
  for (let year = MIN_YEARS; year < currentYear; year++) {
    availableYears.value.push(year);
  }
}
const queryYear = route.query.year
  ? parseInt(route.query.year as string, 10)
  : null;
const selectedYear = ref<number>(
  queryYear && availableYears.value.includes(queryYear)
    ? queryYear
    : availableYears.value[availableYears.value.length - 1],
);

const yearConfigStore = useYearConfigStore();
const { t: $t } = useI18n();

// Issue #867 — single SSE consumer driving the post-create
// "Setting up year… → synced / failed" notifications.  Mirrors the
// pattern in ``ModuleConfig.vue`` (subscribe on pipeline_id transition,
// release on unmount).  Defined here so the templates below can read
// ``yearSyncInFlight`` to gate CSV uploads + module config edits while
// the pipeline runs.
const { subscribe, unsubscribe, isFinishedFor, hasErrorFor } =
  usePipelineStream();

const fetchYearConfig = async () => {
  await yearConfigStore.fetchConfig(selectedYear.value);
};

watch(
  selectedYear,
  async () => {
    try {
      await fetchYearConfig();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to load year data';
      Notify.create({ type: 'negative', message: msg });
    }
  },
  { immediate: true },
);

watch(selectedYear, (year) => {
  void router.replace({ query: { ...route.query, year: String(year) } });
});

// Issue #867 — currently-tracked pipeline_id from the most recent
// create-year call.  When set, ``yearSyncInFlight`` is true and CSV /
// module config controls are disabled (gated below).  Cleared after
// the SSE stream signals success/error so the page returns to the
// normal interactive state.
const activePipelineId = ref<string | null>(null);
const activePipelineYear = ref<number | null>(null);

const yearSyncInFlight = computed(() => {
  const id = activePipelineId.value;
  if (!id) return false;
  // ``isFinishedFor`` flips ``true`` once every job hits FINISHED or
  // the terminal ``stream_closed`` payload arrives — until then we're
  // in flight.  The watch below converts the transition to a
  // success/error notification + cleanup.
  return !isFinishedFor(id).value;
});

watch(
  () =>
    activePipelineId.value
      ? isFinishedFor(activePipelineId.value).value
      : false,
  (finished, wasFinished) => {
    const id = activePipelineId.value;
    if (!id || !finished || wasFinished) return;
    const year = activePipelineYear.value ?? selectedYear.value;
    const failed = hasErrorFor(id).value;
    if (failed) {
      Notify.create({
        type: 'negative',
        message: $t('data_management_year_sync_error', { year }),
        caption: $t('data_management_year_sync_error_caption'),
      });
    } else {
      Notify.create({
        type: 'positive',
        message: $t('data_management_year_sync_success', { year }),
        caption: $t('data_management_year_sync_success_caption'),
      });
      // Refetch the year config so the page reflects the rows the
      // unit_sync handler upserted (carbon_reports etc).
      void fetchYearConfig();
    }
    unsubscribe(id);
    activePipelineId.value = null;
    activePipelineYear.value = null;
  },
);

const handleCreateYear = async () => {
  try {
    const response = await yearConfigStore.createConfig(selectedYear.value);
    Notify.create({
      type: 'positive',
      message: $t('data_management_year_created', { year: selectedYear.value }),
    });

    // Issue #867 — auto-subscribe to the unit_sync pipeline kicked off
    // by the create endpoint.  No pipeline_id means the backend skipped
    // the auto-sync (older deployments / future opt-out flag); fall
    // back gracefully — the operator can still trigger a sync via the
    // module-level recalc affordances.
    const pipelineId = response.pipeline_id ?? null;
    if (pipelineId) {
      activePipelineId.value = pipelineId;
      activePipelineYear.value = selectedYear.value;
      Notify.create({
        type: 'info',
        message: $t('data_management_year_sync_in_progress', {
          year: selectedYear.value,
        }),
        caption: $t('data_management_year_sync_in_progress_caption'),
      });
      await subscribe(pipelineId);
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    Notify.create({ type: 'negative', message: msg });
  }
};

watch(
  () => yearConfigStore.loading,
  (newValue) => {
    if (newValue) {
      Loading.show({ message: $t('data_management_loading') });
    } else {
      Loading.hide();
    }
  },
);

onMounted(() => {
  // intentionally empty — loading is handled by the yearConfigStore.loading watcher
});

// ── Data-entry dialog (provided to child components like ReductionObjectivesSection) ──
const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

function openDataEntryDialog(row: ImportRow, targetType: TargetType | null) {
  // Issue #867 — refuse to open the upload dialog while the
  // ``unit_sync`` pipeline is still running.  Module-level rows depend
  // on the units / carbon_reports it produces; opening the upload
  // before they exist surfaces noisy 404s in the dialog flow.
  if (yearSyncInFlight.value) {
    Notify.create({
      type: 'warning',
      message: $t('data_management_year_sync_in_progress', {
        year: selectedYear.value,
      }),
      caption: $t('data_management_year_sync_in_progress_caption'),
    });
    return;
  }
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
}

provide('openDataEntryDialog', openDataEntryDialog);

async function handleDialogCompleted() {
  await yearConfigStore.fetchConfig(selectedYear.value);
}
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />
    <div class="q-my-xl q-px-xl">
      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="row justify-between items-center">
          <q-card-section class="row justify-between full-width q-pa-none">
            <div class="text-subtitle1">
              {{ $t('data_management_reporting_year') }}
            </div>
            <!--
              Issue #867 — the standalone "Sync units from Accred" button
              was removed.  Year creation now auto-enqueues the unit_sync
              pipeline; the page subscribes to it via SSE and shows real
              progress / success / error notifications driven by the
              stream (no more 5s setTimeout fake success).
            -->
          </q-card-section>

          <q-select
            v-model="selectedYear"
            :options="availableYears"
            outlined
            dense
            class="full-width q-my-md"
          >
            <template #prepend>
              <q-icon name="event" color="accent" size="xs" />
            </template>
          </q-select>

          <div class="text-body2 text-secondary">
            {{ $t('data_management_reporting_year_hint') }}
          </div>
        </div>
      </q-card>

      <!-- Startup: no configuration exists yet -->
      <q-card
        v-if="yearConfigStore.notFound && !yearConfigStore.loading"
        flat
        bordered
        class="q-pa-xl q-mb-xl text-center"
      >
        <q-icon
          name="calendar_today"
          size="64px"
          color="grey-5"
          class="q-mb-md"
        />
        <div class="text-h6 q-mb-sm">
          {{
            $t('data_management_year_not_configured', { year: selectedYear })
          }}
        </div>
        <div class="text-body2 text-secondary q-mb-lg">
          {{ $t('data_management_year_not_configured_hint') }}
        </div>
        <q-btn
          color="primary"
          icon="add"
          :label="$t('data_management_create_year', { year: selectedYear })"
          :loading="yearConfigStore.loading"
          @click="handleCreateYear"
        />
      </q-card>

      <!-- Loading skeleton -->
      <template v-else-if="yearConfigStore.loading && !yearConfigStore.config">
        <q-skeleton type="rect" height="80px" class="q-mb-md" />
        <q-skeleton type="rect" height="200px" class="q-mb-md" />
      </template>

      <template v-if="yearConfigStore.config">
        <temp-files-banner class="q-mb-xl" />
        <!--
          Issue #867 — gate module config + CSV uploads on the
          unit_sync pipeline.  ``q-inner-loading`` keeps the rendered
          state visible (so the operator sees what will be ready) while
          the ``inert`` attribute disables every interactive descendant
          natively (clicks, focus, keyboard).  The ``openDataEntryDialog``
          provider above ALSO refuses to open while the sync is in
          flight — a defense-in-depth check for any path that bypasses
          the visual gate.
        -->
        <div :inert="yearSyncInFlight" class="relative-position">
          <template v-for="module in MODULES_LIST" :key="module">
            <ModuleConfig :module="module" :selected-year="selectedYear" />
          </template>
          <ReductionObjectivesSection :selected-year="selectedYear" />
          <q-inner-loading :showing="yearSyncInFlight" color="primary">
            <div class="text-center q-pa-md">
              <q-spinner-dots size="48px" color="primary" class="q-mb-md" />
              <div class="text-subtitle1">
                {{
                  $t('data_management_year_sync_in_progress', {
                    year: selectedYear,
                  })
                }}
              </div>
              <div class="text-body2 text-secondary">
                {{ $t('data_management_year_sync_in_progress_caption') }}
              </div>
            </div>
          </q-inner-loading>
        </div>
      </template>

      <q-btn
        icon="calendar_month"
        color="accent"
        :label="$t('open_year_for_users')"
        class="text-weight-medium text-capitalize q-mt-md"
        :disable="yearConfigStore.anyModuleIncomplete"
      >
        <q-tooltip v-if="yearConfigStore.anyModuleIncomplete">
          {{ $t('data_management_open_year_disabled_tooltip') }}
        </q-tooltip>
      </q-btn>
    </div>

    <data-entry-dialog
      v-model="showDataEntryDialog"
      :row="dialogCurrentRow || ({} as ImportRow)"
      :year="selectedYear"
      :target-type="dialogTargetType ?? TargetType.DATA_ENTRIES"
      @completed="handleDialogCompleted"
      @progressing="handleDialogCompleted"
    />
  </q-page>
</template>
