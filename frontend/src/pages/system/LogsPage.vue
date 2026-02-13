<script setup lang="ts">
import { onMounted } from 'vue';
import { SYSTEM_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import AuditStatCards from 'src/components/audit/AuditStatCards.vue';
import AuditFilterBar from 'src/components/audit/AuditFilterBar.vue';
import AuditSearchBar from 'src/components/audit/AuditSearchBar.vue';
import AuditTable from 'src/components/audit/AuditTable.vue';
import AuditPagination from 'src/components/audit/AuditPagination.vue';
import AuditDetailDrawer from 'src/components/audit/AuditDetailDrawer.vue';
import { useAuditLogs } from 'src/composables/useAuditLogs';

const {
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
} = useAuditLogs();

onMounted(() => {
  onSearch();
});
</script>

<template>
  <q-page>
    <navigation-header :item="SYSTEM_NAV.SYSTEM_LOGS" />

    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <!-- Stat cards -->
        <AuditStatCards
          :stats="stats"
          :loading="statsLoading"
          class="q-mb-lg"
        />

        <!-- Filter bar -->
        <AuditFilterBar
          :action="actionFilter"
          :entity-type="entityTypeFilter"
          :module="moduleFilter"
          :handler-id="handlerIdFilter"
          :date-range="dateRange"
          class="q-mb-md"
          @update:action="
            actionFilter = $event;
            onFilterChange();
          "
          @update:entity-type="
            entityTypeFilter = $event;
            onFilterChange();
          "
          @update:module="
            moduleFilter = $event;
            onFilterChange();
          "
          @update:handler-id="
            handlerIdFilter = $event;
            onFilterChange();
          "
          @update:date-range="
            dateRange = $event;
            onFilterChange();
          "
        />

        <!-- Search bar + export -->
        <AuditSearchBar
          v-model="searchQuery"
          class="q-mb-md"
          @search="onSearch"
          @export="handleExport"
        />

        <!-- Error banner -->
        <q-banner
          v-if="hasError"
          class="bg-negative text-white q-mb-md"
          rounded
        >
          Failed to load audit logs.
          <template #action>
            <q-btn flat label="Retry" @click="retry" />
          </template>
        </q-banner>

        <!-- Table -->
        <AuditTable
          :rows="logs"
          :loading="isLoading"
          :sort-by="sortBy"
          :sort-desc="sortDesc"
          @sort="onSort"
          @view="openDetail"
          @copy="copyEntry"
        />

        <!-- Pagination -->
        <AuditPagination
          :page="page"
          :page-size="pageSize"
          :total="totalEntries"
          class="q-mt-md"
          @update:page="onPageChange"
          @update:page-size="onPageSizeChange"
        />

        <!-- Detail drawer -->
        <AuditDetailDrawer
          v-model="detailOpen"
          :entry="selectedLog"
          @copy="copyEntry"
        />
      </div>
    </div>
  </q-page>
</template>
