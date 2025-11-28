<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { REPORT_TYPES, type ReportType } from 'src/constant/report';
import type { ModuleState } from 'src/constant/moduleStates';

const { t } = useI18n();

interface ModuleCompletion {
  status: ModuleState;
  outlier_values: number;
}

interface UnitData {
  id: string | number;
  completion:
    | Record<string, ModuleCompletion>
    | Record<string, Record<string, ModuleCompletion>>;
  completion_counts: {
    validated: number;
    in_progress: number;
    default: number;
  };
  unit: string;
  affiliation: string;
  principal_user: string;
  last_update: string;
  outlier_values: number;
}

const props = defineProps<{
  units?: UnitData[];
}>();

const selectedReport = ref<ReportType>('combined');

/**
 * Escapes a CSV field value by wrapping it in quotes if it contains
 * commas, quotes, or newlines, and escaping any quotes within the value.
 */
function escapeCsvField(value: string | number): string {
  const stringValue = String(value);
  // If value contains comma, quote, or newline, wrap in quotes and escape quotes
  if (/[,"\n]/.test(stringValue)) {
    return `"${stringValue.replace(/"/g, '""')}"`;
  }
  return stringValue;
}

function downloadCSV() {
  if (!props.units || props.units.length === 0) return;

  const headers =
    [
      t('backoffice_reporting_row_unit_label'),
      t('backoffice_reporting_row_affiliation_label'),
      t('backoffice_reporting_row_principal_user_label'),
      t('backoffice_reporting_row_last_update_label'),
      t('backoffice_reporting_csv_validated'),
      t('backoffice_reporting_csv_in_progress'),
      t('backoffice_reporting_csv_default'),
      t('backoffice_reporting_row_outlier_values_label'),
    ]
      .map(escapeCsvField)
      .join(',') + '\n';

  const rows = props.units
    .map((u) =>
      [
        u.unit,
        u.affiliation,
        u.principal_user,
        u.last_update,
        u.completion_counts.validated,
        u.completion_counts.in_progress,
        u.completion_counts.default,
        u.outlier_values,
      ]
        .map(escapeCsvField)
        .join(','),
    )
    .join('\n');

  const csv = headers + rows;
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'report.csv';
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div class="grid-3-col q-mt-lg">
    <q-card
      v-for="report in REPORT_TYPES"
      :key="report.value"
      flat
      bordered
      class="q-pa-md cursor-pointer container container--pa-sm"
      :class="{
        'container--selected': selectedReport === report.value,
      }"
      @click="selectedReport = report.value"
    >
      <div class="flex justify-between items-start">
        <div class="flex column q-gutter-sm" style="flex: 1">
          <div class="flex items-center q-gutter-sm">
            <q-icon
              :name="report.icon"
              color="accent"
              size="sm"
              class="q-pa-xs"
            />
            <h3 class="text-h5 text-weight-bold q-mb-none">
              {{ $t(report.titleKey) }}
            </h3>
          </div>
          <p class="text-body2 text-secondary q-mb-none q-mt-sm">
            {{ $t(report.descriptionKey) }}
          </p>
        </div>
        <q-radio
          v-model="selectedReport"
          :val="report.value"
          color="accent"
          size="sm"
        />
      </div>
    </q-card>
  </div>

  <div class="q-mt-lg">
    <div class="container full-width container--pa-none">
      <div class="flex items-center q-gutter-md">
        <div class="bg-accent q-px-md q-mr-xl self-stretch flex items-center">
          <q-icon name="o_warning" size="xs" color="white" />
        </div>
        <div>
          <div class="q-my-lg text-body2">
            <p style="white-space: pre-line">
              {{ $t('backoffice_reporting_generate_formats') }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="q-mt-lg">
    <q-btn
      icon="o_picture_as_pdf"
      color="accent"
      :label="$t('common_export_as_pdf')"
      unelevated
      no-caps
      size="md"
      class="text-weight-medium q-mr-sm"
    />
    <q-btn
      icon="o_table"
      color="accent"
      :label="$t('common_export_as_csv')"
      unelevated
      no-caps
      size="md"
      class="text-weight-medium"
      @click="downloadCSV"
    />
  </div>
</template>
