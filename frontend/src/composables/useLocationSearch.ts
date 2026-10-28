import { nextTick, ref } from 'vue';
import type { QSelect } from 'quasar';
import { searchLocations } from '@/api/locations';
import type { Location, TransportMode } from '@/constant/locations';

// The backend's max `limit`; a shorter page means the results ran out.
const PAGE_SIZE = 20;

/**
 * Server-side typeahead with infinite scroll for one q-select of
 * CO2DestinationInput (#939): `filter` loads page 1 per keystroke,
 * `onVirtualScroll` appends the next page when the last option renders.
 */
export function useLocationSearch(
  transportMode: () => TransportMode | undefined,
) {
  const options = ref<Location[]>([]);
  const loading = ref(false);
  let query = '';
  let page = 1;
  let hasMore = false;
  // Bumped whenever the list is replaced, so a late page for an older list
  // (previous query, previous transport mode) is dropped instead of appended.
  let generation = 0;

  function replace(results: Location[], val: string) {
    generation += 1;
    options.value = results;
    query = val;
    page = 1;
    hasMore = results.length === PAGE_SIZE;
  }

  async function filter(val: string, update: (fn: () => void) => void) {
    const mode = transportMode();
    if (!mode || val.length < 2) {
      update(() => replace([], val));
      return;
    }

    const started = generation;
    loading.value = true;
    try {
      const results = await searchLocations(val, mode, PAGE_SIZE, 1);
      update(() => {
        if (started === generation) replace(results, val);
      });
    } catch (error) {
      console.error('Error fetching locations:', error);
      update(() => {
        if (started === generation) replace([], val);
      });
    } finally {
      loading.value = false;
    }
  }

  async function onVirtualScroll({
    to,
    ref: select,
  }: {
    to: number;
    ref: QSelect;
  }) {
    const mode = transportMode();
    if (!mode || loading.value || !hasMore || to !== options.value.length - 1) {
      return;
    }

    const listed = generation;
    loading.value = true;
    try {
      const results = await searchLocations(query, mode, PAGE_SIZE, page + 1);
      if (listed !== generation) return;
      page += 1;
      hasMore = results.length === PAGE_SIZE;
      options.value = [...options.value, ...results];
      await nextTick();
      select.refresh();
    } catch (error) {
      // Keep the rows already shown; paging resumes with the next search.
      console.error('Error fetching more locations:', error);
      if (listed === generation) hasMore = false;
    } finally {
      loading.value = false;
    }
  }

  function reset() {
    replace([], '');
    loading.value = false;
  }

  return { options, loading, filter, onVirtualScroll, reset };
}
