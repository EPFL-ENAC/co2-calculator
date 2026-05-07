<script setup lang="ts">
/**
 * Plan 310-D — diagnostic tooltip for the in-flight pipeline badge.
 *
 * Renders inside a parent ``<q-badge>`` (or any anchor) via
 * ``<q-tooltip>`` and surfaces what the operator needs to triage
 * a running or failed bulk pipeline without opening devtools:
 *
 * - Pipeline UUID (copy-on-click)
 * - Per-job rows: ``{job_type} · {state}{result?}`` with the
 *   ``status_message`` underneath
 * - Failure cases: error ``status_message`` highlighted in red
 *
 * All data is read from the ``pipelineStream`` store (already
 * populated by ``usePipelineStream`` on the parent component); this
 * component owns no fetching or subscription.
 */

import { computed } from 'vue';
import { copyToClipboard, Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { usePipelineStreamStore } from 'src/stores/pipelineStream';

interface Props {
  pipelineId: string;
}

const props = defineProps<Props>();
const { t } = useI18n();
const store = usePipelineStreamStore();

const jobs = computed(() => store.jobsFor(props.pipelineId));

async function copyPipelineId(): Promise<void> {
  try {
    await copyToClipboard(props.pipelineId);
    Notify.create({
      type: 'positive',
      message: t('data_management_pipeline_id_copied'),
      timeout: 1500,
    });
  } catch {
    Notify.create({
      type: 'negative',
      message: t('data_management_pipeline_id_copy_failed'),
      timeout: 1500,
    });
  }
}

/**
 * Map the backend's IngestionState string to a Quasar color token.
 * FINISHED+ERROR rows render in red regardless of state — the result
 * is what matters for the operator's eye.
 */
function jobColor(state: string | null, result: string | null): string {
  if (state === 'FINISHED' && result === 'ERROR') return 'negative';
  if (state === 'FINISHED') return 'positive';
  if (state === 'RUNNING') return 'info';
  return 'grey-7';
}
</script>

<template>
  <q-tooltip
    anchor="bottom middle"
    self="top middle"
    class="bg-grey-10 q-pa-md"
    :offset="[0, 8]"
    style="max-width: 480px"
  >
    <div class="text-body2" style="min-width: 320px">
      <!-- Pipeline header: UUID + copy button -->
      <div class="row items-center q-gutter-xs q-mb-sm">
        <div class="text-caption text-grey-5">
          {{ $t('data_management_pipeline_id_label') }}
        </div>
        <code class="text-caption text-white">{{ pipelineId }}</code>
        <q-btn
          flat
          dense
          size="xs"
          icon="content_copy"
          color="white"
          @click.stop.prevent="copyPipelineId"
        >
          <q-tooltip>{{ $t('data_management_pipeline_id_copy') }}</q-tooltip>
        </q-btn>
      </div>

      <!-- Empty state — happens during the brief window between
           subscribe and the first ``pipeline-update`` event landing -->
      <div v-if="jobs.length === 0" class="text-caption text-grey-5 q-py-sm">
        {{ $t('data_management_pipeline_no_jobs_yet') }}
      </div>

      <!-- Per-job rows: type, state, result, status_message -->
      <div v-else class="column q-gutter-xs">
        <div
          v-for="job in jobs"
          :key="job.id"
          class="row items-start q-gutter-xs"
        >
          <q-icon
            name="circle"
            size="xs"
            :color="jobColor(job.state, job.result)"
            class="q-mt-xs"
          />
          <div class="col">
            <div class="text-weight-medium text-white">
              {{ job.job_type ?? '?' }}
              <span class="text-caption text-grey-5 q-ml-xs">
                · {{ job.state ?? '?'
                }}{{ job.result ? ' · ' + job.result : '' }}
              </span>
            </div>
            <div
              v-if="job.status_message"
              class="text-caption q-mt-xs"
              :class="
                job.state === 'FINISHED' && job.result === 'ERROR'
                  ? 'text-negative'
                  : 'text-grey-4'
              "
              style="white-space: pre-wrap; word-break: break-word"
            >
              {{ job.status_message }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </q-tooltip>
</template>
