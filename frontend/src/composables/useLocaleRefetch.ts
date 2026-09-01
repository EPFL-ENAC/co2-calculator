import { watch } from 'vue';
import { i18n } from '@/boot/i18n';

/**
 * Re-run a fetch when the user switches language (#2401): row labels,
 * search matching and taxonomy labels are all locale-dependent. The
 * component owning the fetch registers it here with its own current args
 * — one shared trigger, no store-side replay of remembered arguments
 * (which went stale across navigation).
 */
export function useLocaleRefetch(refetch: () => void): void {
  watch(
    () => i18n.global.locale.value,
    () => refetch(),
  );
}
