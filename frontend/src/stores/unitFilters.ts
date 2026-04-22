import { defineStore } from 'pinia';
import { ref, computed, nextTick } from 'vue';

export interface Options {
  label: string;
  value: string | number;
  unit_type_label?: string;
}

export interface PaginationInfo {
  page: number;
  page_size: number;
  total_pages: number;
  total: number;
}

export const useUnitFiltersStore = defineStore('unitFilters', () => {
  // ========== Affiliation State (merged Lvl2 + Lvl3) ==========
  const dataAffiliation = ref<Options[]>([]);
  const paginationAffiliation = ref<PaginationInfo>({
    page: 1,
    page_size: 50,
    total_pages: 1,
    total: 0,
  });
  const loadingAffiliation = ref(false);
  const errorAffiliation = ref<string | null>(null);
  const searchQueryAffiliation = ref<string>('');
  const currentPageAffiliation = ref(1);

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

  // ========== Affiliation Fetch Logic (merged Lvl2 + Lvl3) ==========
  const fetchAffiliationUnits = async (query: string, page: number) => {
    loadingAffiliation.value = true;
    errorAffiliation.value = null;
    try {
      const params = new URLSearchParams();
      if (query) {
        params.append('name', query);
      }
      params.append('page_size', '50');
      params.append('page', page.toString());

      const res = await fetch(
        `/api/v1/backoffice-reporting/affiliations?${params.toString()}`,
      );

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      const units = await res.json();

      const mapped: Options[] = units.map(
        (item: { id: number; name: string; unit_type_label: string }) => ({
          label: item.name,
          value: item.id,
          unit_type_label: item.unit_type_label || '',
        }),
      );

      dataAffiliation.value = page === 1 ? mapped : [...dataAffiliation.value, ...mapped];

      paginationAffiliation.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: mapped.length,
      };
    } catch (e) {
      errorAffiliation.value = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loadingAffiliation.value = false;
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
      params.append('parent_unit_type_label', 'Centre'); // for enac-it for instance
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

  // ========== Affiliation Actions ==========
  const setSearchQueryAffiliation = (query: string) => {
    searchQueryAffiliation.value = query;
    currentPageAffiliation.value = 1;
    if (query === '') {
      dataAffiliation.value = [];
      paginationAffiliation.value = {
        page: 1,
        page_size: 50,
        total_pages: 1,
        total: 0,
      };
    }
    void nextTick(() => fetchAffiliationUnits(query, 1));
  };

  const filterAffiliationUnits = (val: string, update: (cb: () => void) => void) => {
    update(() => {
      setSearchQueryAffiliation(val);
    });
  };

  const resetAffiliationFilters = () => {
    searchQueryAffiliation.value = '';
    currentPageAffiliation.value = 1;
    dataAffiliation.value = [];
    paginationAffiliation.value = {
      page: 1,
      page_size: 50,
      total_pages: 1,
      total: 0,
    };
    errorAffiliation.value = null;
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
    resetAffiliationFilters();
    resetLevel4Filters();
  };

  // ========== Can Load More (for infinite scroll) ==========
  const canLoadMoreAffiliation = computed(
    () =>
      !loadingAffiliation.value &&
      paginationAffiliation.value.page < paginationAffiliation.value.total_pages,
  );
  const canLoadMoreLevel4 = computed(
    () =>
      !loadingLevel4.value &&
      paginationLevel4.value.page < paginationLevel4.value.total_pages,
  );

  // ========== Infinite Scroll Handlers ==========
  const onScrollAffiliation = ({ to }: { to: number }) => {
    const threshold = dataAffiliation.value.length - 5;
    if (to >= threshold && canLoadMoreAffiliation.value) {
      fetchAffiliationUnits(searchQueryAffiliation.value, currentPageAffiliation.value);
    }
  };

  const onScrollLevel4 = ({ to }: { to: number }) => {
    const threshold = dataLevel4.value.length - 5;
    if (to >= threshold && canLoadMoreLevel4.value) {
      fetchLevel4Units(searchQueryLevel4.value, currentPageLevel4.value);
    }
  };

  return {
    // ========== Affiliation ==========
    dataAffiliation,
    paginationAffiliation,
    loadingAffiliation,
    errorAffiliation,
    searchQueryAffiliation,
    currentPageAffiliation,
    canLoadMoreAffiliation,
    filterAffiliationUnits,
    setSearchQueryAffiliation,
    onScrollAffiliation,
    resetAffiliationFilters,

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
