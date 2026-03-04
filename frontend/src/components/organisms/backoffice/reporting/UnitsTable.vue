<script setup lang="ts">
import { computed, ref } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';
import { formatRelativeTime } from 'src/utils/date';

const ROWS_PER_PAGE = 20;
const { locale, t } = useI18n();
const showAllRows = ref(false);

interface UnitReportingData {
  id: string | number;
  unit_name: string; // EN: Unit / FR: Unité
  affiliation: string; // Affiliation filter value
  validation_status: string; // e.g. "3/7"
  principal_user: string; // Source: ACCRED
  last_update: string; // Date of last validation
  highest_result_category: string; // Module name with max tCO2-eq
  total_carbon_footprint: number; // (tCO2-eq)
}

const props = defineProps<{
  units: Array<UnitReportingData>;
  loading: boolean;
}>();

const emit = defineEmits<{
  viewUnit: [unitId: string | number];
}>();

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

const pagination = computed(() => ({
  rowsPerPage: showAllRows.value ? 0 : ROWS_PER_PAGE,
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
    <q-checkbox
      v-model="showAllRows"
      :label="t('common_show_all_rows')"
      color="primary"
      size="sm"
    />
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
  >
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
          {{ p.row.highest_result_category || '—' }}
        </div>
        <q-tooltip v-if="p.row.highest_result_category">
          {{ p.row.highest_result_category }}
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
