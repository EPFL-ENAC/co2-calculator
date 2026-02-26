import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export interface Options {
  label: string;
  value: string | number;
}

export interface PaginationInfo {
  page: number;
  page_size: number;
  total_pages: number;
  total: number;
}

export const useUnitFiltersStore = defineStore('unitFilters', () => {
  // State
  const data = ref<Options[]>([]);
  const pagination = ref<PaginationInfo>({
    page: 1,
    page_size: 50,
    total_pages: 1,
    total: 0,
  });
  const loading = ref(false);
  const error = ref<string | null>(null);

  const searchQuery = ref<string>('');
  const currentPage = ref(1);

  // Core fetch — appends when page > 1, replaces when page === 1
  const fetchUnits = async (query: string, page: number) => {
    loading.value = true;
    error.value = null;
    try {
      const res = await fetch(
        `/api/v1/backoffice/select-units?years=2025&page_size=50&name=${query}&page=${page}`,
      );

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      const json = await res.json();

      const mapped: Options[] = json.data.map(
        (item: { id: number; name: string }) => ({
          label: item.name,
          value: item.id,
        }),
      );

      // Replace on new search (page 1), accumulate on pagination
      data.value = page === 1 ? mapped : [...data.value, ...mapped];

      pagination.value = {
        page: json.page,
        page_size: json.page_size,
        total_pages: json.total_pages,
        total: json.total,
      };
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loading.value = false;
    }
  };

  // Actions
  const setSearchQuery = (query: string) => {
    searchQuery.value = query;
    currentPage.value = 1;
    fetchUnits(query, 1);
  };

  // For Quasar's @filter on QSelect
  const filterUnits = (val: string, update: (cb: () => void) => void) => {
    update(() => {
      setSearchQuery(val);
    });
  };

  const nextPage = () => {
    if (currentPage.value >= pagination.value.total_pages) return;
    if (loading.value) return;

    currentPage.value++;
    fetchUnits(searchQuery.value, currentPage.value);
  };

  const canLoadMore = computed(
    () =>
      !loading.value && pagination.value.page < pagination.value.total_pages,
  );

  const onScroll = ({ to }: { to: number }) => {
    const threshold = data.value.length - 5;
    if (to >= threshold && canLoadMore.value) {
      nextPage();
    }
  };

  const resetFilters = () => {
    searchQuery.value = '';
    currentPage.value = 1;
    data.value = [];
    pagination.value = { page: 1, page_size: 50, total_pages: 1, total: 0 };
    error.value = null;
  };

  return {
    // State
    data,
    pagination,
    loading,
    error,
    searchQuery,
    currentPage,
    // Actions
    filterUnits,
    setSearchQuery,
    nextPage,
    resetFilters,
    onScroll,
    canLoadMore,
  };
});
