<script setup lang="ts">
import { computed } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';
import { formatRelativeTime } from 'src/utils/date';
import type { PaginationState } from 'src/stores/backoffice';

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

const props = defineProps<{
  units: Array<UnitReportingData>;
  pagination?: PaginationState;
  paginationMeta?: PaginationMeta;
  loading: boolean;
}>();

const emit = defineEmits<{
  'update:pagination': [pagination: PaginationState];
  viewUnit: [unitId: string | number];
}>();

const paginationState = computed({
  get: () => ({
    page: props.pagination?.page ?? 1,
    pageSize: props.pagination?.pageSize ?? 10,
    sortBy: props.pagination?.sortBy ?? 'unit_name',
    descending: props.pagination?.descending ?? false,
  }),
  set: (newState: PaginationState) => {
    emit('update:pagination', newState);
  },
});

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
    label: t('backoffice_reporting_column_validation_status'),
    field: 'validation_status',
    align: 'center',
    sortable: true,
  },
  {
    name: 'principal_user',
    label: t('backoffice_reporting_column_principal_user'),
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

const paginationOptions = [10, 25, 50, 100, 5000];

const pagination = computed(() => ({
  page: paginationState.value.page,
  rowsPerPage: paginationState.value.pageSize,
  rowsPerPageOptions: paginationOptions,
  sortBy: paginationState.value.sortBy,
  descending: paginationState.value.descending,
  serverPagination: true,
  totalPages: props.paginationMeta?.total_pages ?? 0,
}));
</script>

<template>
  <div class="flex justify-between items-center q-mb-sm">
    <span class="text-body1 text-weight-medium">
      {{
        t('backoffice_reporting_units_status_label', {
          count: props.units.length,
        })
      }}
    </span>
  </div>

  <q-table
    class="co2-table border shadow-0"
    :rows="props.units"
    :columns="columns"
    row-key="id"
    :pagination="pagination"
    :loading="props.loading"
    flat
    bordered
    @request="
      (request: {
        pagination: {
          page: number;
          rowsPerPage: number;
          sortBy: string;
          descending: boolean;
        };
      }) => {
        emit('update:pagination', {
          page: request.pagination.page,
          pageSize: request.pagination.rowsPerPage,
          sortBy: request.pagination.sortBy,
          descending: request.pagination.descending,
        });
      }
    "
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
      <div class="q-px-sm">
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
