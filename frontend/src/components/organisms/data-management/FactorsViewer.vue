<script setup lang="ts">
// Backoffice factor viewer (#1491) — read-only paginated table of the
// factors stored for one (data entry type, year) scope.  Surfaces
// last_seen_job_id so an operator can spot rows the latest upload did
// not assert (those are swept by the next fully successful upload).
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import type { QTableProps } from 'quasar';
import { enumSubmodule } from 'src/constant/modules';
import { useFactorsStore } from 'src/stores/factors';
import type { BackofficeFactorRow } from 'src/api/factors';

const props = defineProps<{ year: number }>();

const { t } = useI18n();
const factorsStore = useFactorsStore();

const detOptions = Object.entries(enumSubmodule).map(([label, value]) => ({
  label: `${label} (${value})`,
  value,
}));
const selectedDet = ref<number | null>(null);

const rows = ref<BackofficeFactorRow[]>([]);
const loading = ref(false);
const pagination = ref({
  page: 1,
  rowsPerPage: 25,
  rowsNumber: 0,
});

// Columns derive from the rows: the handler response DTO differs per
// data entry type.  Keep id first and last_seen_job_id last.
const columns = computed<QTableProps['columns']>(() => {
  const keys = new Set<string>();
  rows.value.forEach((r) => Object.keys(r).forEach((k) => keys.add(k)));
  const middle = [...keys]
    .filter((k) => k !== 'id' && k !== 'last_seen_job_id')
    .sort();
  const ordered = [
    ...(keys.has('id') ? ['id'] : []),
    ...middle,
    ...(keys.has('last_seen_job_id') ? ['last_seen_job_id'] : []),
  ];
  return ordered.map((k) => ({
    name: k,
    label: k,
    field: k,
    align: 'left' as const,
    sortable: false,
  }));
});

async function fetchPage(page: number, rowsPerPage: number): Promise<void> {
  if (selectedDet.value == null) {
    rows.value = [];
    pagination.value.rowsNumber = 0;
    return;
  }
  loading.value = true;
  try {
    const res = await factorsStore.fetchBackofficeFactors({
      dataEntryTypeId: selectedDet.value,
      year: props.year,
      page,
      pageSize: rowsPerPage,
    });
    rows.value = res.data;
    pagination.value.page = res.pagination.page;
    pagination.value.rowsPerPage = res.pagination.page_size;
    pagination.value.rowsNumber = res.pagination.total;
  } finally {
    loading.value = false;
  }
}

function onRequest(req: {
  pagination: { page: number; rowsPerPage: number };
}): void {
  void fetchPage(req.pagination.page, req.pagination.rowsPerPage);
}

watch([selectedDet, () => props.year], () => {
  void fetchPage(1, pagination.value.rowsPerPage);
});
</script>

<template>
  <q-card flat bordered class="q-pa-md q-mb-xl" data-testid="factors-viewer">
    <q-card-section class="q-pa-none q-mb-md">
      <div class="text-subtitle1">{{ t('factors_viewer_title') }}</div>
      <div class="text-body2 text-secondary">
        {{ t('factors_viewer_hint') }}
      </div>
    </q-card-section>

    <q-select
      v-model="selectedDet"
      :options="detOptions"
      :label="t('factors_viewer_data_entry_type')"
      data-testid="factors-viewer-det-select"
      outlined
      dense
      emit-value
      map-options
      clearable
      class="q-mb-md"
      style="max-width: 420px"
    />

    <q-table
      v-if="selectedDet != null"
      v-model:pagination="pagination"
      :rows="rows"
      :columns="columns"
      :loading="loading"
      row-key="id"
      flat
      bordered
      dense
      :rows-per-page-options="[10, 25, 50, 100]"
      :no-data-label="t('factors_viewer_no_data')"
      data-testid="factors-viewer-table"
      @request="onRequest"
    />
  </q-card>
</template>
