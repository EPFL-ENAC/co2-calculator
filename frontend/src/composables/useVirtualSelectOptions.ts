import { ref, computed, watch, type Ref } from 'vue';

const PAGE_SIZE = 50;

export function useVirtualSelectOptions(
  fullOptions: Ref<Array<{ label: string; value: string }>>,
  selectedValue?: Ref<string | null | undefined>,
) {
  const searchQuery = ref('');
  const displayedOptions = ref<Array<{ label: string; value: string }>>([]);

  const filteredOptions = computed(() => {
    const q = searchQuery.value.toLowerCase();
    if (!q) return fullOptions.value;
    return fullOptions.value.filter(
      (o) =>
        o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
    );
  });

  function loadFirstPage() {
    displayedOptions.value = filteredOptions.value.slice(0, PAGE_SIZE);
  }

  // Reset when the source list changes (e.g. submodule switch)
  watch(fullOptions, () => {
    searchQuery.value = '';
    loadFirstPage();
  });

  const visibleOptions = computed(() => {
    const sel = selectedValue?.value;
    if (sel && !displayedOptions.value.some((o) => o.value === sel)) {
      const found = fullOptions.value.find((o) => o.value === sel);
      if (found) return [found, ...displayedOptions.value];
    }
    return displayedOptions.value;
  });

  function filterFn(
    val: string,
    update: (cb: () => void) => void,
    abort?: () => void,
  ) {
    void abort;
    update(() => {
      searchQuery.value = val;
      // filteredOptions recomputes synchronously — take the first page
      displayedOptions.value = filteredOptions.value.slice(0, PAGE_SIZE);
    });
  }

  function onVirtualScroll({ to }: { to: number }) {
    const threshold = displayedOptions.value.length - 5;
    if (
      to >= threshold &&
      displayedOptions.value.length < filteredOptions.value.length
    ) {
      const nextBatch = filteredOptions.value.slice(
        displayedOptions.value.length,
        displayedOptions.value.length + PAGE_SIZE,
      );
      displayedOptions.value = [...displayedOptions.value, ...nextBatch];
    }
  }

  return { visibleOptions, filterFn, onVirtualScroll };
}
