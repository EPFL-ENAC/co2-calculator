import { defineStore } from 'pinia';
import { ref, computed, nextTick } from 'vue';

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
  // ========== Level 2 State ==========
  const dataLevel2 = ref<Options[]>([]);
  const paginationLevel2 = ref<PaginationInfo>({
    page: 1,
    page_size: 50,
    total_pages: 1,
    total: 0,
  });
  const loadingLevel2 = ref(false);
  const errorLevel2 = ref<string | null>(null);
  const searchQueryLevel2 = ref<string>('');
  const currentPageLevel2 = ref(1);

  // ========== Level 3 State ==========
  const dataLevel3 = ref<Options[]>([]);
  const paginationLevel3 = ref<PaginationInfo>({
    page: 1,
    page_size: 50,
    total_pages: 1,
    total: 0,
  });
  const loadingLevel3 = ref(false);
  const errorLevel3 = ref<string | null>(null);
  const searchQueryLevel3 = ref<string>('');
  const currentPageLevel3 = ref(1);

  // ========== Level 4 State ==========
  const dataLevel4 = ref<Options[]>([]);
  const paginationLevel4 = ref<PaginationInfo>({
    page: 1,
    page_size: 50,
    total_pages: 1,
    total: 0,
  });
  const loadingLevel4 = ref(false);
  const errorLevel4 = ref<string | null>(null);
  const searchQueryLevel4 = ref<string>('');
  const currentPageLevel4 = ref(1);

  // ========== Level 2 Fetch Logic ==========
  const fetchLevel2Units = async (query: string, page: number) => {
    loadingLevel2.value = true;
    errorLevel2.value = null;
    try {
      // Build query params: level=2, unit_type_labels for Service central and Faculté
      const params = new URLSearchParams();
      params.append('level', '2');
      params.append('unit_type_labels', 'Service central');
      params.append('unit_type_labels', 'Faculté');
      if (query) {
        params.append('name', query);
      }
      params.append('page_size', '50');
      params.append('page', page.toString());

      const res = await fetch(
        `/api/v1/backoffice-reporting/units?${params.toString()}`,
      );

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      // The response is a list of units, not paginated JSON
      const units = await res.json();

      const mapped: Options[] = units.map(
        (item: { id: number; name: string }) => ({
          label: item.name,
          value: item.id,
        }),
      );

      // Replace on new search (page 1), accumulate on pagination
      dataLevel2.value = page === 1 ? mapped : [...dataLevel2.value, ...mapped];

      // Since backend returns the full list, we need to track pagination manually
      // For now, assume all data is loaded since the endpoint doesn't return pagination info
      // This may need adjustment if backend adds pagination
      paginationLevel2.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: mapped.length,
      };
    } catch (e) {
      errorLevel2.value = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loadingLevel2.value = false;
    }
  };

  // ========== Level 3 Fetch Logic ==========
  const fetchLevel3Units = async (query: string, page: number) => {
    loadingLevel3.value = true;
    errorLevel3.value = null;
    try {
      // Build query params: level=3, unit_type_label=Institut
      const params = new URLSearchParams();
      params.append('level', '3');
      params.append('unit_type_label', 'Institut');
      if (query) {
        params.append('name', query);
      }
      params.append('page_size', '50');
      params.append('page', page.toString());

      const res = await fetch(
        `/api/v1/backoffice-reporting/units?${params.toString()}`,
      );

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      const units = await res.json();

      const mapped: Options[] = units.map(
        (item: { id: number; name: string }) => ({
          label: item.name,
          value: item.id,
        }),
      );

      dataLevel3.value = page === 1 ? mapped : [...dataLevel3.value, ...mapped];

      paginationLevel3.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: mapped.length,
      };
    } catch (e) {
      errorLevel3.value = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loadingLevel3.value = false;
    }
  };

  // ========== Level 4 Fetch Logic ==========
  const fetchLevel4Units = async (query: string, page: number) => {
    loadingLevel4.value = true;
    errorLevel4.value = null;
    try {
      // Build query params: level=4, parent_unit_type_label=Institut
      const params = new URLSearchParams();
      params.append('level', '4');
      params.append('parent_unit_type_label', 'Institut');
      // params.append('parent_unit_type_label', 'Centre'); // for enac-it for instance
      if (query) {
        params.append('name', query);
      }
      params.append('page_size', '50');
      params.append('page', page.toString());

      const res = await fetch(
        `/api/v1/backoffice-reporting/units?${params.toString()}`,
      );

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      const units = await res.json();

      const mapped: Options[] = units.map(
        (item: { id: number; name: string }) => ({
          label: item.name,
          value: item.id,
        }),
      );

      dataLevel4.value = page === 1 ? mapped : [...dataLevel4.value, ...mapped];

      paginationLevel4.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: mapped.length,
      };
    } catch (e) {
      errorLevel4.value = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loadingLevel4.value = false;
    }
  };

  // ========== Level 2 Actions ==========
  const setSearchQueryLevel2 = (query: string) => {
    searchQueryLevel2.value = query;
    currentPageLevel2.value = 1;
    // Reset data when clearing search to ensure fresh fetch
    if (query === '') {
      dataLevel2.value = [];
      paginationLevel2.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: 0,
      };
    }
    void nextTick(() => fetchLevel2Units(query, 1));
  };

  const filterLevel2Units = (val: string, update: (cb: () => void) => void) => {
    update(() => {
      setSearchQueryLevel2(val);
    });
  };

  const resetLevel2Filters = () => {
    searchQueryLevel2.value = '';
    currentPageLevel2.value = 1;
    dataLevel2.value = [];
    paginationLevel2.value = {
      page: 1,
      page_size: 50,
      total_pages: 1,
      total: 0,
    };
    errorLevel2.value = null;
  };

  // ========== Level 3 Actions ==========
  const setSearchQueryLevel3 = (query: string) => {
    searchQueryLevel3.value = query;
    currentPageLevel3.value = 1;
    // Reset data when clearing search to ensure fresh fetch
    if (query === '') {
      dataLevel3.value = [];
      paginationLevel3.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: 0,
      };
    }
    void nextTick(() => fetchLevel3Units(query, 1));
  };

  const filterLevel3Units = (val: string, update: (cb: () => void) => void) => {
    update(() => {
      setSearchQueryLevel3(val);
    });
  };

  const resetLevel3Filters = () => {
    searchQueryLevel3.value = '';
    currentPageLevel3.value = 1;
    dataLevel3.value = [];
    paginationLevel3.value = {
      page: 1,
      page_size: 50,
      total_pages: 1,
      total: 0,
    };
    errorLevel3.value = null;
  };

  // ========== Level 4 Actions ==========
  const setSearchQueryLevel4 = (query: string) => {
    searchQueryLevel4.value = query;
    currentPageLevel4.value = 1;
    // Reset data when clearing search to ensure fresh fetch
    if (query === '') {
      dataLevel4.value = [];
      paginationLevel4.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: 0,
      };
    }
    void nextTick(() => fetchLevel4Units(query, 1));
  };

  const filterLevel4Units = (val: string, update: (cb: () => void) => void) => {
    update(() => {
      setSearchQueryLevel4(val);
    });
  };

  const resetLevel4Filters = () => {
    searchQueryLevel4.value = '';
    currentPageLevel4.value = 1;
    dataLevel4.value = [];
    paginationLevel4.value = {
      page: 1,
      page_size: 50,
      total_pages: 1,
      total: 0,
    };
    errorLevel4.value = null;
  };

  // ========== Global Reset ==========
  const resetFilters = () => {
    resetLevel2Filters();
    resetLevel3Filters();
    resetLevel4Filters();
  };

  // ========== Can Load More (for infinite scroll) ==========
  const canLoadMoreLevel2 = computed(
    () =>
      !loadingLevel2.value &&
      paginationLevel2.value.page < paginationLevel2.value.total_pages,
  );
  const canLoadMoreLevel3 = computed(
    () =>
      !loadingLevel3.value &&
      paginationLevel3.value.page < paginationLevel3.value.total_pages,
  );
  const canLoadMoreLevel4 = computed(
    () =>
      !loadingLevel4.value &&
      paginationLevel4.value.page < paginationLevel4.value.total_pages,
  );

  // ========== Infinite Scroll Handlers ==========
  const onScrollLevel2 = ({ to }: { to: number }) => {
    const threshold = dataLevel2.value.length - 5;
    if (to >= threshold && canLoadMoreLevel2.value) {
      // For now, we just reload since we don't have true pagination from backend
      fetchLevel2Units(searchQueryLevel2.value, currentPageLevel2.value);
    }
  };

  const onScrollLevel3 = ({ to }: { to: number }) => {
    const threshold = dataLevel3.value.length - 5;
    if (to >= threshold && canLoadMoreLevel3.value) {
      fetchLevel3Units(searchQueryLevel3.value, currentPageLevel3.value);
    }
  };

  const onScrollLevel4 = ({ to }: { to: number }) => {
    const threshold = dataLevel4.value.length - 5;
    if (to >= threshold && canLoadMoreLevel4.value) {
      fetchLevel4Units(searchQueryLevel4.value, currentPageLevel4.value);
    }
  };

  return {
    // ========== Level 2 ==========
    dataLevel2,
    paginationLevel2,
    loadingLevel2,
    errorLevel2,
    searchQueryLevel2,
    currentPageLevel2,
    canLoadMoreLevel2,
    filterLevel2Units,
    setSearchQueryLevel2,
    onScrollLevel2,
    resetLevel2Filters,

    // ========== Level 3 ==========
    dataLevel3,
    paginationLevel3,
    loadingLevel3,
    errorLevel3,
    searchQueryLevel3,
    currentPageLevel3,
    canLoadMoreLevel3,
    filterLevel3Units,
    setSearchQueryLevel3,
    onScrollLevel3,
    resetLevel3Filters,

    // ========== Level 4 ==========
    dataLevel4,
    paginationLevel4,
    loadingLevel4,
    errorLevel4,
    searchQueryLevel4,
    currentPageLevel4,
    canLoadMoreLevel4,
    filterLevel4Units,
    setSearchQueryLevel4,
    onScrollLevel4,
    resetLevel4Filters,

    // ========== Global ==========
    resetFilters,
  };
});
