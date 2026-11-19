<script setup lang="ts">
import { onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { runtimeConfig } from '@/config/runtime';

import { BACKOFFICE_NAV } from '@/constant/navigation';
import NavigationHeader from '@/components/organisms/backoffice/NavigationHeader.vue';
import AuditStatCards from '@/components/audit/AuditStatCards.vue';
import AuditFilterBar from '@/components/audit/AuditFilterBar.vue';
import AuditSearchBar from '@/components/audit/AuditSearchBar.vue';
import AuditTable from '@/components/audit/AuditTable.vue';
import AuditPagination from '@/components/audit/AuditPagination.vue';
import AuditDetailDrawer from '@/components/audit/AuditDetailDrawer.vue';
import { useAuditLogs } from '@/composables/useAuditLogs';

const { t } = useI18n();

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

// Operations links of this deployment, from APP_OPS_* (#3244). An empty
// value hides its link, and the card is hidden when every link is empty.
const { opsLinks } = runtimeConfig;
const opsColumns = [
  {
    title: 'logs_ops_gitops',
    links: [{ label: 'logs_ops_link_application', url: opsLinks.argocd }],
  },
  {
    title: 'logs_ops_monitoring',
    links: [
      { label: 'logs_ops_link_dashboard', url: opsLinks.grafanaDashboard },
      { label: 'logs_ops_link_graphs', url: opsLinks.grafanaGraphs },
    ],
  },
  {
    title: 'logs_ops_app_logs',
    links: [{ label: 'logs_ops_link_logs', url: opsLinks.logs }],
  },
  {
    title: 'logs_ops_platform',
    links: [{ label: 'logs_ops_link_console', url: opsLinks.openshift }],
  },
]
  .map((column) => ({
    ...column,
    links: column.links.filter((link) => link.url),
  }))
  .filter((column) => column.links.length > 0);
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_LOGS" />
    <div v-if="opsColumns.length > 0" class="q-my-xl q-px-xl">
      <div class="container full-width">
        <q-card class="q-pa-lg" data-testid="ops-links">
          <div class="text-subtitle1 text-weight-bold q-mb-md text-uppercase">
            {{ t('logs_ops_environment', { name: runtimeConfig.environment }) }}
          </div>
          <div class="row q-col-gutter-md">
            <div
              v-for="column in opsColumns"
              :key="column.title"
              class="col-12 col-sm-6 col-md-3"
            >
              <div class="text-subtitle2 q-mb-sm text-weight-medium">
                {{ t(column.title) }}
              </div>
              <div class="q-gutter-sm">
                <q-btn
                  v-for="link in column.links"
                  :key="link.label"
                  :label="t(link.label)"
                  color="primary"
                  size="sm"
                  outline
                  :href="link.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="full-width"
                />
              </div>
            </div>
          </div>
        </q-card>
      </div>
    </div>
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
          {{ t('audit_msg_load_failed') }}
          <template #action>
            <q-btn flat :label="t('audit_btn_retry')" @click="retry" />
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
