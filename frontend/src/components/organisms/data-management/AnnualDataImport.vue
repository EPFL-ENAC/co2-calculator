<script setup lang="ts">
import { ref, computed } from 'vue';
import { useFilesStore } from 'src/stores/files';
import type {
  SyncJobResponse,
  ImportRow,
} from 'src/stores/backofficeDataManagement';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import {
  IngestionResult,
  IngestionState,
  IngestionMethod,
  TargetType,
} from 'src/stores/backofficeDataManagement';
import { useYearConfigStore, type SyncJobSummary } from 'src/stores/yearConfig';
import { useI18n } from 'vue-i18n';
import DataEntryDialog from './DataEntryDialog.vue';

const filesStore = useFilesStore();
const yearConfigStore = useYearConfigStore();
const { t: $t } = useI18n();

interface Props {
  year: number;
}
const props = defineProps<Props>();

const BASE_IMPORT_ROWS: Omit<
  ImportRow,
  'lastDataJob' | 'lastApiDataJob' | 'lastFactorJob'
>[] = [
  {
    key: 'headcount-member',
    labelKey: 'headcount',
    labelDataEntryKey: 'headcount-member',
    moduleTypeId: 1,
    dataEntryTypeId: 1,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'headcount-student',
    labelKey: 'headcount',
    labelDataEntryKey: 'headcount-student',
    moduleTypeId: 1,
    dataEntryTypeId: 2,
    hasFactors: true,
    hasApi: false,
    hasData: false,
  },
  {
    key: 'professional-travel',
    labelKey: 'professional-travel',
    labelDataEntryKey: 'professional-travel-train',
    moduleTypeId: 2,
    dataEntryTypeId: 21,
    factorVariant: 'train',
    hasFactors: true,
    hasApi: false,
    other: 'data_management_other_train_stations',
    hasOtherUpload: true,
    hasData: true,
  },
  {
    key: 'professional-travel',
    labelKey: 'professional-travel',
    labelDataEntryKey: 'professional-travel-plane',
    moduleTypeId: 2,
    dataEntryTypeId: 20,
    factorVariant: 'plane',
    hasFactors: true,
    hasApi: true,
    other: 'data_management_other_airports',
    hasOtherUpload: true,
    hasData: true,
  },
  {
    key: 'buildings',
    labelKey: 'buildings',
    labelDataEntryKey: 'buildings-rooms',
    moduleTypeId: 3,
    dataEntryTypeId: 30,
    hasFactors: true,
    hasApi: false,
    other: 'data_management_other_institution_rooms',
    hasOtherUpload: true,
    hasData: true,
  },
  {
    key: 'buildings_energy_combustion',
    labelKey: 'buildings',
    labelDataEntryKey: 'buildings-combustion',
    moduleTypeId: 3,
    dataEntryTypeId: 31,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'process-emissions',
    labelKey: 'process-emissions',
    moduleTypeId: 8,
    dataEntryTypeId: 50,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'equipment',
    labelKey: 'equipment-electric-consumption',
    moduleTypeId: 4,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'purchases_common',
    labelKey: 'purchase-common',
    moduleTypeId: 5,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'purchases_additional',
    labelKey: 'purchase-additional_purchases',
    moduleTypeId: 5,
    dataEntryTypeId: 67,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'research_facilities',
    labelKey: 'research-facilities',
    moduleTypeId: 6,
    dataEntryTypeId: 70,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'research_facilities_animal',
    labelKey: 'research-facilities.mice_and_fish_animal_facilities',
    moduleTypeId: 6,
    dataEntryTypeId: 71,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'external_clouds',
    labelKey: 'external-cloud-and-ai.cloud-services',
    moduleTypeId: 7,
    dataEntryTypeId: 40,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'external_ai',
    labelKey: 'external-cloud-and-ai.ai-services',
    moduleTypeId: 7,
    dataEntryTypeId: 41,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'food',
    labelKey: 'food',
    moduleTypeId: 10,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'waste',
    labelKey: 'waste',
    moduleTypeId: 11,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'commuting',
    labelKey: 'commuting',
    moduleTypeId: 9,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'embodied_energy',
    labelKey: 'embodied_energy',
    moduleTypeId: 12,
    hasFactors: false,
    hasApi: false,
    isDisabled: true,
    hasData: true,
  },
];

// ── Pure helpers (no reactive side-effects) ───────────────────────────────────

function findJob(
  jobs: SyncJobSummary[],
  moduleTypeId: number,
  targetType: TargetType | null,
  dataEntryTypeId?: number,
  ingestionMethod?: IngestionMethod,
): SyncJobSummary | undefined {
  const candidates = jobs.filter(
    (j) => j.module_type_id === moduleTypeId && j.target_type === targetType,
  );

  if (dataEntryTypeId !== undefined) {
    return candidates.find(
      (j) =>
        j.data_entry_type_id === dataEntryTypeId &&
        j.ingestion_method === ingestionMethod?.valueOf(),
    );
  }
  return candidates[0];
}

function toSyncJobResponse(job: SyncJobSummary): SyncJobResponse {
  return {
    job_id: job.job_id,
    module_type_id: job.module_type_id,
    data_entry_type_id: job.data_entry_type_id,
    year: job.year,
    target_type: job.target_type as TargetType,
    state: job.state as IngestionState,
    result: job.result as IngestionResult,
    status_message: job.status_message,
    meta: job.meta,
  };
}

function importInfo(job: SyncJobResponse | undefined) {
  if (!job?.meta) return null;
  const meta = job.meta as Record<string, unknown>;
  const filePath = (meta.file_path as string) || '';
  return {
    rows: (meta.rows_processed as number) || 0,
    fileName: filePath.split('/').pop() || '',
  };
}

// ── Computed: reads from store cache, parent owns the fetch ───────────────────

const importRows = computed<ImportRow[]>(() => {
  const jobs = yearConfigStore.latestJobs;
  return BASE_IMPORT_ROWS.map((row) => {
    const dataJob = findJob(
      jobs,
      row.moduleTypeId,
      0,
      row.dataEntryTypeId,
      IngestionMethod.CSV,
    );
    const apiDataJob = row.hasApi
      ? findJob(
          jobs,
          row.moduleTypeId,
          0,
          row.dataEntryTypeId,
          IngestionMethod.API,
        )
      : undefined;
    const factorJob = findJob(
      jobs,
      row.moduleTypeId,
      1,
      row.dataEntryTypeId,
      IngestionMethod.CSV,
    );

    return {
      ...row,
      lastDataJob: dataJob ? toSyncJobResponse(dataJob) : undefined,
      lastFactorJob: factorJob ? toSyncJobResponse(factorJob) : undefined,
      lastApiDataJob: apiDataJob ? toSyncJobResponse(apiDataJob) : undefined,
    };
  });
});

// ── Button helpers ────────────────────────────────────────────────────────────

function dataButtonColor(row: ImportRow): string {
  if (row.isDisabled) return 'grey-4';
  if (!row.lastDataJob) return 'accent';
  if (row.lastDataJob.result === 2) return 'negative';
  if (row.lastDataJob.result === 1) return 'warning';
  return 'positive';
}

function factorButtonColor(row: ImportRow): string {
  if (row.isDisabled) return 'grey-4';
  if (!row.lastFactorJob) return 'accent';
  if (row.lastFactorJob.result === 2) return 'negative';
  if (row.lastFactorJob.result === 1) return 'warning';
  return 'positive';
}

function dataButtonLabel(row: ImportRow): string {
  if (row.isDisabled) return '';
  return row.lastDataJob
    ? $t('data_management_reupload_data')
    : $t('data_management_add_data');
}

function factorButtonLabel(row: ImportRow): string {
  if (row.isDisabled) return '';
  return row.lastFactorJob
    ? $t('data_management_reupload_factors')
    : $t('data_management_add_factors');
}

// ── CSV download ──────────────────────────────────────────────────────────────

function downloadLastCsv(row: ImportRow, targetType: TargetType) {
  const job =
    targetType === TargetType.DATA_ENTRIES
      ? row.lastDataJob
      : row.lastFactorJob;
  if (!job?.meta) return;
  const filePath = (job.meta as Record<string, unknown>)
    .processed_file_path as string;
  if (!filePath) return;
  const a = document.createElement('a');
  //  add /api/v1/files to prefix?
  a.href = `/api/v1/files/${filePath}`;
  console.log(a.href);
  a.download = filePath.split('/').pop() || filePath;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ── Dialog ────────────────────────────────────────────────────────────────────

const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

function openDataEntryDialog(row: ImportRow, targetType: TargetType | null) {
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
}

// Re-fetch after upload so the store cache (and this view) updates
async function handleJobCompleted() {
  await yearConfigStore.fetchConfig(props.year);
}

async function handleJobProgressing(job: SyncJobResponse) {
  console.log('Job progressing:', job);

  await yearConfigStore.fetchConfig(props.year);
}
</script>

<template>
  <q-card flat bordered class="q-pa-md q-mb-xl">
    <div class="text-h5 text-weight-medium">
      <q-icon name="file_download" color="accent" size="sm" class="on-left" />
      <span>{{ $t('data_management_annual_data_import') }}</span>
    </div>
    <div class="q-my-md">
      {{ $t('data_management_annual_data_import_hint') }}
    </div>

    <q-banner class="bg-grey-2 text-grey-8">
      <q-icon name="info" size="xs" class="on-left" />
      <span class="q-ml-sm">
        {{
          filesStore.tempFiles.length > 0
            ? $t('data_management_temp_files_uploaded', {
                count: filesStore.tempFiles.length,
              })
            : $t('data_management_no_temp_files_uploaded')
        }}
      </span>
      <q-btn
        v-if="filesStore.tempFiles.length > 0"
        no-caps
        outline
        color="negative"
        icon="delete"
        size="sm"
        :label="$t('data_management_delete_temp_files')"
        class="text-weight-medium on-right"
        @click="filesStore.deleteTempFiles()"
      />
    </q-banner>

    <q-banner inline-actions class="q-px-none">
      <template #action>
        <q-btn
          no-caps
          outline
          color="secondary"
          icon="file_download"
          size="sm"
          :label="$t('data_management_download_csv_templates')"
          class="text-weight-medium"
        />
      </template>
      <div>
        {{
          $t('data_management_data_imports_count', { count: importRows.length })
        }}
      </div>
    </q-banner>

    <q-markup-table flat bordered>
      <thead>
        <tr>
          <th align="left">{{ $t('data_management_category') }}</th>
          <th align="left">{{ $t('data_management_data') }}</th>
          <th align="left">{{ $t('data_management_factor') }}</th>
          <th align="left">{{ $t('data_management_column_other') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in importRows" :key="row.key">
          <!-- Category -->
          <td class="text-weight-medium" align="left">
            {{ $t(row.labelKey) }}
            <span v-if="row.labelDataEntryKey"
              >({{ $t(row.labelDataEntryKey) }})</span
            >
            <q-badge
              v-if="row.isDisabled"
              color="grey-4"
              text-color="grey-8"
              :label="$t('data_management_tbd')"
              class="q-ml-sm"
            />
          </td>

          <!-- Data -->
          <td align="left">
            <div
              v-if="row.hasData"
              class="flex flex-row gap-1 justify-left items-center"
              style="gap: 1rem"
            >
              <q-spinner-rings
                v-if="row.lastDataJob?.state === IngestionState.RUNNING"
                color="grey"
              >
                <q-tooltip>
                  <div class="text-left">
                    {{
                      row.lastDataJob?.status_message ||
                      $t('data_management_processing')
                    }}
                  </div>
                </q-tooltip>
              </q-spinner-rings>
              <q-btn
                :color="dataButtonColor(row)"
                icon="add"
                size="sm"
                :label="dataButtonLabel(row)"
                class="text-weight-medium"
                :disable="row.isDisabled"
                @click="openDataEntryDialog(row, TargetType.DATA_ENTRIES)"
              />
              <q-icon
                v-if="
                  row.lastDataJob?.result === IngestionResult.WARNING ||
                  row.lastDataJob?.result === IngestionResult.ERROR
                "
                :name="outlinedInfo"
                size="sm"
                class="cursor-pointer"
                :aria-label="$t('module-info-label')"
              >
                <!-- tooltip with detail errors  or warnings -->
                <q-tooltip
                  v-if="
                    row.lastDataJob?.result === IngestionResult.WARNING ||
                    row.lastDataJob?.result === IngestionResult.ERROR
                  "
                >
                  <div class="text-left">
                    {{ row.lastDataJob?.status_message }}:
                    <span
                      v-if="
                        row.lastDataJob?.meta?.error !==
                        row.lastDataJob?.status_message
                      "
                      class="text-negative"
                    >
                      {{ row.lastDataJob?.meta?.error || '' }}
                    </span>
                    <hr />
                    <div
                      v-for="(key, value, index) in row.lastDataJob?.meta
                        ?.stats || []"
                      :key="index"
                    >
                      {{ key }}: {{ value }}
                    </div>
                  </div>
                </q-tooltip>
              </q-icon>
              <div
                v-if="importInfo(row.lastDataJob)"
                class="q-mt-xs text-caption text-grey-7 flex flex-row gap-4 justify-between"
              >
                <div v-if="row.hasApi && row?.lastApiDataJob" class="q-ma-xs">
                  api: {{ importInfo(row?.lastApiDataJob)!.rows }}
                  {{ $t('data_management_rows_imported') }}
                  <span>/ </span>
                </div>
                <div class="q-ma-xs">
                  data:
                  {{ importInfo(row?.lastDataJob)!.rows }}
                  {{ $t('data_management_rows_imported') }}
                </div>
                <div class="row items-center q-gutter-xs">
                  <span>{{ importInfo(row?.lastDataJob)!.fileName }}</span>
                  <q-btn
                    flat
                    dense
                    round
                    icon="download"
                    size="xs"
                    color="grey-6"
                    @click="downloadLastCsv(row, TargetType.DATA_ENTRIES)"
                  >
                    <q-tooltip>{{
                      $t('data_management_download_last_csv')
                    }}</q-tooltip>
                  </q-btn>
                </div>
              </div>
            </div>
            <span v-else class="text-grey-5">—</span>
          </td>

          <!-- Factors -->
          <td align="left">
            <div
              v-if="row.hasFactors"
              class="flex flex-row gap-1 justify-between"
            >
              <q-btn
                :color="factorButtonColor(row)"
                icon="add"
                size="sm"
                :label="factorButtonLabel(row)"
                class="text-weight-medium"
                :disable="row.isDisabled"
                @click="openDataEntryDialog(row, TargetType.FACTORS)"
              />
              <div
                v-if="importInfo(row.lastFactorJob)"
                class="q-mt-xs text-caption text-grey-7 flex flex-row gap-1"
              >
                <div>
                  {{ importInfo(row.lastFactorJob)!.rows }}
                  {{ $t('data_management_rows_imported') }}
                </div>
                <div class="row items-center q-gutter-xs">
                  <span>{{ importInfo(row.lastFactorJob)!.fileName }}</span>
                  <q-btn
                    flat
                    dense
                    round
                    icon="download"
                    size="xs"
                    color="grey-6"
                    @click="downloadLastCsv(row, TargetType.FACTORS)"
                  >
                    <q-tooltip>{{
                      $t('data_management_download_last_csv')
                    }}</q-tooltip>
                  </q-btn>
                </div>
              </div>
            </div>
            <span v-else class="text-grey-5">—</span>
          </td>

          <!-- Other -->
          <td align="left">
            <template v-if="row.other">
              <div class="q-mb-xs text-caption text-grey-7">
                {{ $t(row.other) }}
              </div>
              <q-btn
                v-if="row.hasOtherUpload"
                no-caps
                outline
                color="accent"
                icon="file_upload"
                size="sm"
                :label="$t('data_management_upload_reference')"
                class="text-weight-medium"
                disable
              >
                <q-tooltip>{{ $t('data_management_tbd') }}</q-tooltip>
              </q-btn>
            </template>
          </td>
        </tr>
      </tbody>
    </q-markup-table>

    <data-entry-dialog
      v-model="showDataEntryDialog"
      :row="dialogCurrentRow || ({} as ImportRow)"
      :year="year"
      :target-type="dialogTargetType"
      @completed="handleJobCompleted"
      @progressing="handleJobProgressing"
    />
  </q-card>
</template>
