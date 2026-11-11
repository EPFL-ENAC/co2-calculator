<script setup lang="ts">
import { onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import { BACKOFFICE_NAV } from '@/constant/navigation';
import NavigationHeader from '@/components/organisms/backoffice/NavigationHeader.vue';
import AuditStatCards from '@/components/audit/AuditStatCards.vue';
import AuditFilterBar from '@/components/audit/AuditFilterBar.vue';
import AuditSearchBar from '@/components/audit/AuditSearchBar.vue';
import AuditTable from '@/components/audit/AuditTable.vue';
import AuditPagination from '@/components/audit/AuditPagination.vue';
import AuditDetailDrawer from '@/components/audit/AuditDetailDrawer.vue';
import { useAuditLogs } from '@/composables/useAuditLogs';
import { systemLinks } from '@/config/systemLinks';

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

// Operations links of the institution (#500), from APP_SYSTEM_LINKS.
const environments = systemLinks();
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_LOGS" />
    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <div class="q-gutter-md">
          <p v-if="environments.length === 0" class="text-body2 text-secondary">
            {{ $t('logs_page_no_system_links') }}
          </p>
          <q-card v-for="env in environments" :key="env.name" class="q-pa-lg">
            <div class="text-subtitle1 text-weight-bold q-mb-md text-uppercase">
              {{ env.name }} Environment
            </div>

            <div class="row q-col-gutter-md">
              <!-- GitOps Column -->
              <div class="col-12 col-sm-6 col-md-3">
                <div class="text-subtitle2 q-mb-sm text-weight-medium">
                  GitOps (ArgoCD)
                </div>
                <div class="q-gutter-sm">
                  <q-btn
                    v-for="(link, idx) in env.gitops"
                    :key="`gitops-${idx}`"
                    :label="link.label"
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

              <!-- Monitoring Column -->
              <div class="col-12 col-sm-6 col-md-3">
                <div class="text-subtitle2 q-mb-sm text-weight-medium">
                  Monitoring (Grafana)
                </div>
                <div class="q-gutter-sm">
                  <q-btn
                    v-for="(link, idx) in env.monitoring"
                    :key="`monitoring-${idx}`"
                    :label="link.label"
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

              <!-- App Logs Column -->
              <div class="col-12 col-sm-6 col-md-3">
                <div class="text-subtitle2 q-mb-sm text-weight-medium">
                  App Logs
                </div>
                <div class="q-gutter-sm">
                  <q-btn
                    v-for="(link, idx) in env.appLogs"
                    :key="`logs-${idx}`"
                    :label="link.label"
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

              <!-- OpenShift Platform Column -->
              <div class="col-12 col-sm-6 col-md-3">
                <div class="text-subtitle2 q-mb-sm text-weight-medium">
                  OpenShift
                </div>
                <div class="q-gutter-sm">
                  <q-btn
                    v-for="(link, idx) in env.platform"
                    :key="`platform-${idx}`"
                    :label="link.label"
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
