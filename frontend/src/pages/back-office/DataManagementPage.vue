<script setup lang="ts">
import { computed, ref, watch, provide } from 'vue';
import { storeToRefs } from 'pinia';
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
import { usePipelineStateStore } from 'src/stores/pipelineState';
import { usePipelineStream } from 'src/composables/usePipelineStream';
import { Notify, Loading } from 'quasar';
import { useI18n } from 'vue-i18n';

const route = useRoute();
const router = useRouter();

const yearConfigStore = useYearConfigStore();
// Year selection is store-owned (single source of truth) so a dropdown
// change trickles down to every config composable without prop drilling.
const { availableYears, selectedYear } = storeToRefs(yearConfigStore);

// Honour a ?year= deep link on entry; the store already defaults to the
// latest available year otherwise.
const queryYear = route.query.year
  ? parseInt(route.query.year as string, 10)
  : null;
if (queryYear && availableYears.value.includes(queryYear)) {
  selectedYear.value = queryYear;
}
const pipelineStateStore = usePipelineStateStore();
const { t: $t } = useI18n();

// Issue #867 — single ``usePipelineStream`` consumer driving:
//   1. (U1) post-create "Setting up year… → synced/failed" notifications
//      for the unit_sync pipeline_id returned by POST year-configuration.
//   2. (U4) re-attach of the SSE watcher to year-level pipelines on
//      mount + year change.  The Pinia stores live in memory and reset
//      on hard reload, so an in-flight unit-sync would otherwise lose
//      its watcher across the reload boundary.  ``ModuleConfig.vue``
//      already covers the per-module rehydrate path; year-level
//      pipelines carry no ``module_type_id`` and need their own channel.
const { subscribe, unsubscribe, isFinishedFor, hasErrorFor } =
  usePipelineStream();
let lastYearLevelSubscriptions = new Set<string>();

async function rehydrateYearLevelPipelines(year: number): Promise<void> {
  await pipelineStateStore.loadYearLevelFor(year);
  const next = new Set<string>(
    pipelineStateStore.getYearLevelPipelineIds(year),
  );

  for (const id of lastYearLevelSubscriptions) {
    if (!next.has(id)) unsubscribe(id);
  }
  const subscribePromises: Array<Promise<void>> = [];
  for (const id of next) {
    if (!lastYearLevelSubscriptions.has(id)) {
      subscribePromises.push(subscribe(id));
    }
  }
  lastYearLevelSubscriptions = next;
  await Promise.all(subscribePromises);
}

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

// U4 — re-attach SSE watcher for year-level pipelines on mount + year
// change.  Failure is non-fatal (page just runs without live progress
// for year-level pipelines, same UX as before #867).  We log rather
// than toast so a transient hiccup doesn't crowd the year-config error
// notification path.
watch(
  selectedYear,
  async (year) => {
    try {
      await rehydrateYearLevelPipelines(year);
    } catch (err) {
      console.warn(
        '[DataManagementPage] failed to rehydrate year-level pipelines',
        err,
      );
    }
  },
  { immediate: true },
);

// U1 — currently-tracked pipeline_id from the most recent create-year
// call.  While set, ``yearSyncInFlight`` is true and CSV / module
// config controls are disabled.  Cleared after the SSE stream signals
// success/error so the page returns to the normal interactive state.
const activePipelineId = ref<string | null>(null);
const activePipelineYear = ref<number | null>(null);

const yearSyncInFlight = computed(() => {
  // In-flight signal (in-memory) — covers the create-year session
  // window before the SSE stream signals completion.
  const id = activePipelineId.value;
  if (id && !isFinishedFor(id).value) return true;
  // #1234-followup (Guilbert 2026-05-20): durable signal that survives
  // a page refresh. ``configuration_completed`` is stamped by
  // ``unit_sync_handler`` on SUCCESS; while it's ``null`` the year is
  // still being provisioned. Without this branch, a refresh during
  // provisioning clears ``activePipelineId`` and the inert/loader
  // vanished prematurely — exactly the bug Guilbert reported.
  if (
    yearConfigStore.config &&
    yearConfigStore.config.configuration_completed == null
  ) {
    return true;
  }
  return false;
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

// U5 — wire the "Open year for users" button to flip is_started=true.
const handleOpenForUsers = async () => {
  try {
    await yearConfigStore.openForUsers(selectedYear.value);
    Notify.create({
      type: 'positive',
      message: $t('data_management_year_opened_success', {
        year: selectedYear.value,
      }),
    });
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

          <!-- Visibility chip: at-a-glance flag for whether the year is open
               to non-admin users in their workspace year selector. -->
          <q-chip
            v-if="yearConfigStore.config"
            data-testid="year-open-status-chip"
            :color="yearConfigStore.config.is_started ? 'positive' : 'grey-4'"
            :text-color="yearConfigStore.config.is_started ? 'white' : 'grey-9'"
            :icon="yearConfigStore.config.is_started ? 'lock_open' : 'lock'"
            dense
            square
            class="q-mb-sm"
          >
            {{
              yearConfigStore.config.is_started
                ? $t('data_management_year_is_open')
                : $t('data_management_year_is_not_open')
            }}
          </q-chip>

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
            <ModuleConfig :module="module" />
          </template>
          <ReductionObjectivesSection />
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
        v-if="yearConfigStore.config && !yearSyncInFlight"
        icon="calendar_month"
        color="accent"
        :label="$t('open_year_for_users')"
        class="text-weight-medium text-capitalize q-mt-md"
        :loading="yearConfigStore.loading"
        :disable="
          yearConfigStore.anyModuleIncomplete ||
          !!yearConfigStore.config?.is_started
        "
        data-testid="open-year-for-users-btn"
        @click="handleOpenForUsers"
      >
        <q-tooltip v-if="yearConfigStore.config?.is_started">
          {{ $t('backoffice-data-management-year-already-open') }}
        </q-tooltip>
        <q-tooltip v-else-if="yearConfigStore.anyModuleIncomplete">
          {{ $t('backoffice-data-management-open-year-disabled') }}
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
