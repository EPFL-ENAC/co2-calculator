import { computed, nextTick, ref } from 'vue';
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
  const loadError = ref(false);
  const query = ref('');
  let page = 1;
  let hasMore = false;
  // Bumped when a search, a page load or a reset starts: only the latest
  // request may touch the list, the loading flag or the error.
  let request = 0;

  // The `#no-option` wording: an empty list is a failure, a too-short
  // query or a real "no match", never a silent blank.
  const emptyLabel = computed(() => {
    if (loadError.value) return 'module_options_load_error';
    if (query.value.length < 2) return 'common_type_to_search';
    return 'common_no_search_results';
  });

  function replace(results: Location[], val: string) {
    options.value = results;
    query.value = val;
    page = 1;
    hasMore = results.length === PAGE_SIZE;
  }

  async function filter(val: string, update: (fn: () => void) => void) {
    const mode = transportMode();
    const text = val.trim();
    const seq = ++request;
    loading.value = false;
    loadError.value = false;
    // Mirrors the backend's min_length=2 on the trimmed query.
    if (!mode || text.length < 2) {
      update(() => replace([], text));
      return;
    }

    loading.value = true;
    try {
      const results = await searchLocations(text, mode, PAGE_SIZE, 1);
      update(() => {
        if (seq === request) replace(results, text);
      });
    } catch (error) {
      console.error('Error fetching locations:', error);
      update(() => {
        if (seq !== request) return;
        replace([], text);
        loadError.value = true;
      });
    } finally {
      if (seq === request) loading.value = false;
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

    const seq = ++request;
    loading.value = true;
    try {
      const results = await searchLocations(
        query.value,
        mode,
        PAGE_SIZE,
        page + 1,
      );
      if (seq !== request) return;
      page += 1;
      hasMore = results.length === PAGE_SIZE;
      options.value = [...options.value, ...results];
      await nextTick();
      select.refresh();
    } catch (error) {
      // Keep the rows already shown and say the list stops short.
      console.error('Error fetching more locations:', error);
      if (seq !== request) return;
      hasMore = false;
      loadError.value = true;
    } finally {
      if (seq === request) loading.value = false;
    }
  }

  function reset() {
    request += 1;
    replace([], '');
    loading.value = false;
    loadError.value = false;
  }

  return {
    options,
    loading,
    loadError,
    emptyLabel,
    filter,
    onVirtualScroll,
    reset,
  };
}
