<script setup lang="ts">
import { computed } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';
import { formatRelativeTime } from 'src/utils/date';
import { useBackofficeStore } from 'src/stores/backoffice';
import { ROLES } from 'src/constant/roles';

interface UnitReportingData {
  id: string | number;
  unit_name: string; // EN: Unit / FR: Unité
  affiliation: string; // Affiliation filter value
  validation_status: string; // e.g. "3/7"
  principal_user: string; // Source: ACCRED
  last_update: string; // Date of last validation
  highest_result_category: string; // Module name with max tCO₂-eq
  total_carbon_footprint: number; // (tCO₂-eq)
}

interface PaginationMeta {
  page: number;
  page_size: number;
  total_pages: number;
  total: number;
}

const { locale, t } = useI18n();
const backofficeStore = useBackofficeStore();

const props = defineProps<{
  units: Array<UnitReportingData>;
  paginationMeta?: PaginationMeta;
  loading: boolean;
  selectedYearsCount?: number;
}>();

const isMultiYear = computed(() => (props.selectedYearsCount ?? 1) > 1);

const emit = defineEmits<{
  'request-data': [];
  viewUnit: [unitId: string | number];
}>();

function onRequest(request: {
  pagination: {
    page: number;
    rowsPerPage: number;
    sortBy: string;
    descending: boolean;
  };
}) {
  const currentSortBy = backofficeStore.unitsPagination.sortBy;
  const currentDescending = backofficeStore.unitsPagination.descending;
  const newSortBy = request.pagination.sortBy;

  console.log('🔍 [UnitsTable] onRequest received:', {
    page: request.pagination.page,
    rowsPerPage: request.pagination.rowsPerPage,
    sortBy: newSortBy,
  });

  console.log('🔍 [UnitsTable] Sort change detection:', {
    current: { sortBy: currentSortBy, descending: currentDescending },
    new: { sortBy: newSortBy },
  });

  let finalDescending;
  let finalSortBy = newSortBy;

  if (!newSortBy) {
    // No sorting requested
    finalDescending = false;
    finalSortBy = undefined;
  } else if (newSortBy === currentSortBy) {
    // Same column clicked - toggle direction or reset on 3rd click
    if (!currentDescending) {
      // Was ascending, toggle to descending
      finalDescending = true;
      console.log('🔄 [UnitsTable] Toggling to descending');
    } else {
      // Was descending, reset to no sort
      finalDescending = false;
      finalSortBy = undefined;
      console.log('🔄 [UnitsTable] Resetting to no sort');
    }
  } else {
    // Different column - start with ascending
    finalDescending = false;
    console.log('🆕 [UnitsTable] New column, starting with ascending');
  }

  backofficeStore.unitsPagination.page = request.pagination.page;
  backofficeStore.unitsPagination.pageSize = request.pagination.rowsPerPage;
  backofficeStore.unitsPagination.sortBy = finalSortBy;
  backofficeStore.unitsPagination.descending = finalDescending;

  console.log(
    '✅ [UnitsTable] Store updated to:',
    JSON.stringify(backofficeStore.unitsPagination, null, 2),
  );

  emit('request-data');
}

const paginationOptions = [10, 25, 50, 100, { label: 'All', value: 5000 }];

const pagination = computed(() => ({
  page: backofficeStore.unitsPagination.page,
  rowsPerPage: backofficeStore.unitsPagination.pageSize,
  rowsPerPageOptions: paginationOptions,
  sortBy: backofficeStore.unitsPagination.sortBy,
  descending: backofficeStore.unitsPagination.descending,
  rowsNumber: props.paginationMeta?.total ?? 0,
}));

const columns = computed<QTableColumn[]>(() => [
  {
    name: 'unit_name',
    label: t('backoffice_reporting_column_unit'),
    field: 'unit_name',
    align: 'left',
    sortable: true,
  },
  {
    name: 'affiliation',
    label: t('backoffice_reporting_column_affiliation'),
    field: 'affiliation',
    align: 'left',
    sortable: true,
  },
  {
    name: 'validation_status',
    label: isMultiYear.value
      ? t('backoffice_reporting_column_years_completed')
      : t('backoffice_reporting_column_validation_status'),
    field: 'validation_status',
    align: 'center',
    sortable: true,
  },
  {
    name: 'principal_user',
    label: t(ROLES.PrincipalUser),
    field: 'principal_user',
    align: 'left',
    sortable: true,
  },
  {
    name: 'last_update',
    label: t('backoffice_reporting_column_last_update'),
    field: 'last_update',
    align: 'left',
    sortable: true,
  },
  {
    name: 'highest_result_category',
    label: t('backoffice_reporting_column_highest_category'),
    field: 'highest_result_category',
    align: 'left',
    sortable: true,
  },
  {
    name: 'total_carbon_footprint',
    label: t('backoffice_reporting_column_total_footprint'),
    field: 'total_carbon_footprint',
    align: 'right',
    sortable: true,
  },
  {
    name: 'action',
    label: t('backoffice_reporting_column_view'),
    field: 'id',
    align: 'center',
  },
]);

// const paginationOptions = [10, 25, 50, 100, 5000];

// const pagination = computed(() => ({
//   page: props.pagination.page,
//   rowsPerPage: props.pagination.pageSize,
//   rowsPerPageOptions: paginationOptions,
//   sortBy: props.pagination.sortBy,
//   descending: props.pagination.descending,
//   rowsNumber: props.paginationMeta?.total ?? 0,
// }));
</script>

<template>
  <div class="flex justify-between items-center q-mb-sm">
    <span class="text-body1 text-weight-medium">
      {{
        t('backoffice_reporting_units_status_label', {
          count: paginationMeta?.total,
        })
      }}
    </span>
  </div>
  <q-table
    v-model:pagination="pagination"
    :binary-state-sort="true"
    :rows="props.units"
    :columns="columns"
    :server-pagination="true"
    row-key="id"
    :loading="props.loading"
    class="co2-table border shadow-0"
    :no-data-label="$t('common_no_items')"
    :rows-per-page-label="$t('rows_per_page')"
    flat
    bordered
    @request="onRequest"
  >
    <template #pagination="scope">
      <q-btn
        icon="chevron_left"
        color="grey-8"
        round
        dense
        flat
        :disable="scope.isFirstPage"
        @click="scope.prevPage"
      />
      <div v-if="scope.pagesNumber > 1" class="q-px-sm">
        {{ scope.pagination.page }} / {{ scope.pagesNumber }}
      </div>
      <q-btn
        icon="chevron_right"
        color="grey-8"
        round
        dense
        flat
        :disable="scope.isLastPage"
        @click="scope.nextPage"
      />
    </template>

    <template #body-cell-unit_name="p">
      <q-td :props="p" class="text-weight-bold">
        {{ p.row.unit_name }}
      </q-td>
    </template>

    <template #body-cell-validation_status="p">
      <q-td :props="p">
        <q-badge outline color="primary" :label="p.row.validation_status" />
      </q-td>
    </template>

    <template #body-cell-last_update="p">
      <q-td :props="p">
        {{
          p.row.last_update
            ? formatRelativeTime(p.row.last_update, locale)
            : '—'
        }}
      </q-td>
    </template>

    <template #body-cell-highest_result_category="p">
      <q-td :props="p">
        <div class="ellipsis" style="max-width: 150px">
          {{ $t(p.row.highest_result_category) || '—' }}
        </div>
        <q-tooltip v-if="p.row.highest_result_category">
          {{ $t(p.row.highest_result_category) }}
        </q-tooltip>
      </q-td>
    </template>

    <template #body-cell-total_carbon_footprint="p">
      <q-td :props="p" class="text-weight-medium">
        {{ p.row.total_carbon_footprint.toLocaleString() }}
        <small>tCO₂-eq</small>
      </q-td>
    </template>

    <template #body-cell-action="p">
      <q-td :props="p">
        <q-btn
          flat
          round
          color="grey-7"
          icon="o_visibility"
          size="sm"
          @click="emit('viewUnit', p.row.id)"
        >
          <q-tooltip>{{ t('common_view_details') }}</q-tooltip>
        </q-btn>
      </q-td>
    </template>
  </q-table>
</template>

<!-- Not scoped: .co2-table's rules reach into Quasar's rendered table internals
     (thead/tbody/td/tr), which do not receive scoped style attributes. -->
<style lang="scss">
@use 'src/css/02-tokens' as tokens;

.co2-table {
  border: 1px solid tokens.$container-default-border;
  border-radius: tokens.$table-border-radius;
  font-size: tokens.$text-size-sm;

  /* height or max-height is important for sticky header */
  max-height: tokens.$table-max-height;
  overflow-y: auto;

  th {
    font-size: tokens.$text-size-sm;
  }

  thead tr th {
    position: sticky;
    z-index: tokens.$table-header-z-index;
    background-color: tokens.$table-bg-odd;
  }

  thead tr:first-child th {
    top: 0;
  }

  .q-table td {
    border: none;
  }

  tbody .q-tr:nth-child(even) {
    background-color: tokens.$table-bg-even;
  }

  tr {
    &::before {
      display: none !important;
    }
  }

  &--selectable {
    tbody tr {
      cursor: pointer;

      &.selected > td {
        border-top: 1px solid tokens.$container-selected-hover-border !important;
        border-bottom: 1px solid tokens.$container-selected-hover-border !important;
      }

      &.selected:first-child > td {
        border-top: none !important;
        border-bottom: 1px solid tokens.$container-selected-hover-border !important;
      }

      &.selected:last-child > td {
        border-top: 1px solid tokens.$container-selected-hover-border !important;
        border-bottom: none !important;
      }
    }
  }

  .square-button {
    padding: tokens.$spacing-sm tokens.$spacing-sm;
  }
}
</style>
