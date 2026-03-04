<script setup lang="ts">
import { computed, ref } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';
import { formatRelativeTime } from 'src/utils/date';
import { ModuleState } from 'src/constant/moduleStates';

const ROWS_PER_PAGE = 20;
const { locale, t } = useI18n();
const showAllRows = ref(false);

interface ModuleCompletion {
  status: ModuleState;
  outlier_values: number;
}

const props = defineProps<{
  units: Array<{
    id: string | number;
    completion:
      | Record<string, ModuleCompletion>
      | Record<string, Record<string, ModuleCompletion>>;
    completion_counts: {
      validated: number;
      in_progress: number;
      default: number;
    };
    unit: number;
    affiliation: string;
    principal_user: string;
    last_update: string;
    outlier_values: number;
    expected_total?: number;
  }>;
  loading: boolean;
}>();

const emit = defineEmits<{
  viewUnit: [unitId: string | number];
}>();

function handleView(unitId: string | number) {
  emit('viewUnit', unitId);
}

const columns = computed<QTableColumn[]>(() => [
  {
    name: 'completion',
    label: t('backoffice_reporting_row_completion_label'),
    field: 'completion',
    align: 'left',
    sortable: true,
    sort: (a: (typeof props.units)[0], b: (typeof props.units)[0]) => {
      return a.completion_counts.validated - b.completion_counts.validated;
    },
  },
  {
    name: 'unit',
    label: t('backoffice_reporting_row_unit_label'),
    field: 'unit',
    align: 'left',
    sortable: true,
  },
  {
    name: 'affiliation',
    label: t('backoffice_reporting_row_affiliation_label'),
    field: 'affiliation',
    align: 'left',
    sortable: true,
  },
  {
    name: 'principal_user',
    label: t('backoffice_reporting_row_principal_user_label'),
    field: 'principal_user',
    align: 'left',
    sortable: true,
  },
  {
    name: 'last_update',
    label: t('backoffice_reporting_row_last_update_label'),
    field: 'last_update',
    align: 'left',
    sortable: true,
  },
  {
    name: 'outlier_values',
    label: t('backoffice_reporting_row_outlier_values_label'),
    field: 'outlier_values',
    align: 'left',
    sortable: true,
  },
  {
    name: 'action',
    label: t('backoffice_reporting_row_action_label'),
    field: 'action',
    align: 'right',
    sortable: false,
  },
]);

const pagination = computed(() => {
  if (showAllRows.value) {
    return {
      rowsPerPage: 0, // 0 means show all rows
    };
  }
  return {
    rowsPerPage: ROWS_PER_PAGE,
  };
});
</script>

<template>
  <div class="flex justify-between items-center q-mb-sm">
    <span class="text-body1 text-weight-medium">{{
      $t('backoffice_reporting_units_status_label', {
        count: props.units.length,
      })
    }}</span>
    <q-checkbox
      v-model="showAllRows"
      :label="$t('common_show_all_rows')"
      color="accent"
      size="sm"
    />
  </div>
  <q-table
    class="co2-table border"
    flat
    :rows="props.units"
    :columns="columns"
    row-key="id"
    :pagination="pagination"
    :rows-per-page-options="showAllRows ? [] : [ROWS_PER_PAGE]"
    :loading="props.loading"
    :hide-pagination="showAllRows"
    :virtual-scroll="showAllRows"
    :virtual-scroll-item-size="48"
    :virtual-scroll-sticky-size-start="48"
  >
    <template #body="{ row, rowIndex }">
      <q-tr
        class="q-tr--no-hover"
        :class="{
          'bg-grey-1': rowIndex % 2 === 1,
        }"
      >
        <!-- Completion -->
        <q-td key="completion">
          <q-badge
            :color="
              row.expected_total &&
              typeof row.expected_total === 'number' &&
              row.completion_counts.validated === row.expected_total
                ? 'green'
                : 'red'
            "
            :label="
              row.expected_total &&
              typeof row.expected_total === 'number' &&
              row.completion_counts.validated === row.expected_total
                ? t('common_filter_complete')
                : t('common_filter_incomplete')
            "
            class="text-white"
          />
        </q-td>

        <!-- Unit -->
        <q-td key="unit">
          <span>{{ row.unit }}</span>
        </q-td>

        <!-- Affiliation -->
        <q-td key="affiliation">
          <span>{{ row.affiliation }}</span>
        </q-td>

        <!-- Principal User -->
        <q-td key="principal_user">
          <span>{{ row.principal_user }}</span>
        </q-td>

        <!-- Last Update -->
        <q-td key="last_update">
          <span>{{ formatRelativeTime(row.last_update, locale) }}</span>
        </q-td>

        <!-- Outlier Values -->
        <q-td key="outlier_values">
          <q-badge
            v-if="row.outlier_values > 0"
            color="red"
            :label="`${row.outlier_values} ${t('backoffice_reporting_errors_label')}`"
            class="text-white"
          />
          <span v-else class="text-grey-6">—</span>
        </q-td>

        <!-- Action -->
        <q-td key="action" class="text-center">
          <q-btn
            icon="o_visibility"
            unelevated
            no-caps
            size="sm"
            class="btn-secondary"
            @click="handleView(row.id)"
          />
        </q-td>
      </q-tr>
    </template>
  </q-table>
</template>
