import { ref, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { Notify } from 'quasar';
import {
  fetchAuditLogs,
  fetchAuditStats,
  fetchAuditLogDetail,
  exportAuditLogs,
  type AuditAction,
  type AuditLogEntry,
  type AuditLogDetail,
  type AuditStats,
  type AuditQueryParams,
} from 'src/api/audit';

export function useAuditLogs() {
  const router = useRouter();
  const route = useRoute();

  // ── Filter state ────────────────────────────────────────────────
  const actionFilter = ref<AuditAction | null>(
    (route.query.action as AuditAction) || null,
  );
  const entityTypeFilter = ref<string | null>(
    (route.query.entity_type as string) || null,
  );
  const moduleFilter = ref<string | null>(
    (route.query.module as string) || null,
  );
  const handlerIdFilter = ref<string | null>(
    (route.query.handler_id as string) || null,
  );
  const dateRange = ref<{ from: string; to: string } | null>(
    route.query.date_from && route.query.date_to
      ? {
          from: route.query.date_from as string,
          to: route.query.date_to as string,
        }
      : null,
  );
  const searchQuery = ref<string>((route.query.search as string) || '');

  // ── Pagination state ───────────────────────────────────────────
  const page = ref<number>(
    route.query.page ? parseInt(route.query.page as string, 10) : 1,
  );
  const pageSize = ref<number>(
    route.query.page_size ? parseInt(route.query.page_size as string, 10) : 25,
  );
  const totalEntries = ref<number>(0);

  // ── Table state ────────────────────────────────────────────────
  const logs = ref<AuditLogEntry[]>([]);
  const isLoading = ref(false);
  const hasError = ref(false);
  const sortBy = ref<string>((route.query.sort_by as string) || 'changed_at');
  const sortDesc = ref<boolean>(
    route.query.sort_desc !== undefined
      ? route.query.sort_desc === 'true'
      : true,
  );

  // ── Stats ──────────────────────────────────────────────────────
  const stats = ref<AuditStats>({
    total_entries: 0,
    creates: 0,
    reads: 0,
    updates: 0,
    deletes: 0,
  });
  const statsLoading = ref(false);

  // ── Detail drawer ──────────────────────────────────────────────
  const selectedLog = ref<AuditLogDetail | null>(null);
  const detailOpen = ref(false);

  // ── Computed ───────────────────────────────────────────────────
  const lastPage = computed(() =>
    Math.max(1, Math.ceil(totalEntries.value / pageSize.value)),
  );
  const showingStart = computed(() =>
    totalEntries.value > 0 ? (page.value - 1) * pageSize.value + 1 : 0,
  );
  const showingEnd = computed(() =>
    Math.min(page.value * pageSize.value, totalEntries.value),
  );

  // ── Params builder ─────────────────────────────────────────────
  function buildParams(): AuditQueryParams {
    const params: AuditQueryParams = {
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_desc: sortDesc.value,
    };
    if (actionFilter.value) params.action = actionFilter.value;
    if (entityTypeFilter.value) params.entity_type = entityTypeFilter.value;
    if (moduleFilter.value) params.module = moduleFilter.value;
    if (handlerIdFilter.value) params.handler_id = handlerIdFilter.value;
    if (dateRange.value) {
      params.date_from = dateRange.value.from;
      params.date_to = dateRange.value.to;
    }
    if (searchQuery.value) params.search = searchQuery.value;
    return params;
  }

  // ── URL sync ───────────────────────────────────────────────────
  function syncToUrl() {
    const query: Record<string, string> = {};
    if (actionFilter.value) query.action = actionFilter.value;
    if (entityTypeFilter.value) query.entity_type = entityTypeFilter.value;
    if (moduleFilter.value) query.module = moduleFilter.value;
    if (handlerIdFilter.value) query.handler_id = handlerIdFilter.value;
    if (dateRange.value) {
      query.date_from = dateRange.value.from;
      query.date_to = dateRange.value.to;
    }
    if (searchQuery.value) query.search = searchQuery.value;
    if (page.value > 1) query.page = String(page.value);
    if (pageSize.value !== 25) query.page_size = String(pageSize.value);
    if (sortBy.value !== 'changed_at') query.sort_by = sortBy.value;
    if (!sortDesc.value) query.sort_desc = 'false';

    router.replace({ query });
  }

  // ── Data fetching ──────────────────────────────────────────────
  async function fetchLogs() {
    isLoading.value = true;
    hasError.value = false;
    try {
      const result = await fetchAuditLogs(buildParams());
      logs.value = result.data;
      totalEntries.value = result.pagination.total;
    } catch (e) {
      hasError.value = true;
      console.error('Failed to fetch audit logs:', e);
    } finally {
      isLoading.value = false;
    }
  }

  async function loadStats() {
    statsLoading.value = true;
    try {
      stats.value = await fetchAuditStats(buildParams());
    } catch (e) {
      console.error('Failed to fetch audit stats:', e);
    } finally {
      statsLoading.value = false;
    }
  }

  // ── Actions ────────────────────────────────────────────────────
  function onSearch() {
    page.value = 1;
    syncToUrl();
    fetchLogs();
    loadStats();
  }

  function onFilterChange() {
    page.value = 1;
    syncToUrl();
    fetchLogs();
    loadStats();
  }

  function onSort(column: string) {
    if (sortBy.value === column) {
      sortDesc.value = !sortDesc.value;
    } else {
      sortBy.value = column;
      sortDesc.value = true;
    }
    syncToUrl();
    fetchLogs();
  }

  function onPageChange(n: number) {
    page.value = n;
    syncToUrl();
    fetchLogs();
  }

  function onPageSizeChange(n: number) {
    pageSize.value = n;
    page.value = 1;
    syncToUrl();
    fetchLogs();
  }

  async function openDetail(id: number) {
    try {
      selectedLog.value = await fetchAuditLogDetail(id);
      detailOpen.value = true;
    } catch {
      Notify.create({
        color: 'negative',
        message: 'Failed to load audit log detail',
        position: 'top',
        timeout: 3000,
      });
    }
  }

  function copyEntry(entry: AuditLogEntry | AuditLogDetail) {
    navigator.clipboard.writeText(JSON.stringify(entry, null, 2));
    Notify.create({
      color: 'positive',
      message: 'Copied to clipboard',
      position: 'top',
      timeout: 2000,
    });
  }

  async function handleExport(format: 'csv' | 'json') {
    try {
      const blob = await exportAuditLogs(buildParams(), format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const today = new Date().toISOString().slice(0, 10);
      a.download = `audit_export_${today}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      Notify.create({
        color: 'positive',
        message: `Exported as ${format.toUpperCase()}`,
        position: 'top',
        timeout: 2000,
      });
    } catch {
      Notify.create({
        color: 'negative',
        message: 'Export failed',
        position: 'top',
        timeout: 3000,
      });
    }
  }

  function retry() {
    fetchLogs();
    loadStats();
  }

  return {
    // Filter state
    actionFilter,
    entityTypeFilter,
    moduleFilter,
    handlerIdFilter,
    dateRange,
    searchQuery,
    // Pagination
    page,
    pageSize,
    totalEntries,
    lastPage,
    showingStart,
    showingEnd,
    // Table
    logs,
    isLoading,
    hasError,
    sortBy,
    sortDesc,
    // Stats
    stats,
    statsLoading,
    // Detail
    selectedLog,
    detailOpen,
    // Actions
    onSearch,
    onFilterChange,
    onSort,
    onPageChange,
    onPageSizeChange,
    openDetail,
    copyEntry,
    handleExport,
    retry,
    fetchLogs,
    loadStats,
  };
}
