import { ref } from 'vue';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { api } from '@/api/http';
import type { PipelineJobListEntry } from '@/stores/pipelineOperationsConsole';

/**
 * Manual recovery of a stale RUNNING job (owning pod died mid-job).
 * The button only renders on ``is_stale`` rows, matching the endpoint's
 * own 409 rule; success requeues the job (state → NOT_STARTED) and the
 * safety poller re-dispatches it within one sweep. ``refetch`` refreshes
 * the caller's listing after a successful requeue.
 */
export function usePipelineJobRecovery(refetch: () => Promise<unknown>) {
  const { t } = useI18n();
  const recovering = ref<Set<number>>(new Set());

  async function recoverJob(j: PipelineJobListEntry): Promise<void> {
    recovering.value.add(j.job_id);
    try {
      await api.post(`sync/jobs/${j.job_id}/recover`);
      Notify.create({
        type: 'positive',
        message: t('pipeops_recover_success'),
        timeout: 1800,
      });
      await refetch();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : t('pipeops_recover_failed');
      Notify.create({ type: 'negative', message: msg });
    } finally {
      recovering.value.delete(j.job_id);
    }
  }

  return { recovering, recoverJob };
}
