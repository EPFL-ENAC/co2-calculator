<script setup lang="ts">
import { onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { SYSTEM_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import AuditStatCards from 'src/components/audit/AuditStatCards.vue';
import AuditFilterBar from 'src/components/audit/AuditFilterBar.vue';
import AuditSearchBar from 'src/components/audit/AuditSearchBar.vue';
import AuditTable from 'src/components/audit/AuditTable.vue';
import AuditPagination from 'src/components/audit/AuditPagination.vue';
import AuditDetailDrawer from 'src/components/audit/AuditDetailDrawer.vue';
import { useAuditLogs } from 'src/composables/useAuditLogs';

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

interface EnvironmentLink {
  label: string;
  url: string;
}

interface EnvironmentConfig {
  name: string;
  gitops: EnvironmentLink[];
  monitoring: EnvironmentLink[];
  appLogs: EnvironmentLink[];
  platform: EnvironmentLink[];
}

const environments: EnvironmentConfig[] = [
  {
    name: 'dev',
    gitops: [
      {
        label: 'GitOps',
        url: 'https://openshift-gitops-server-openshift-gitops.apps.ocpitsd0001.xaas.epfl.ch/applications/openshift-gitops/co2-calculator-dev?view=tree&resource=',
      },
    ],
    monitoring: [
      {
        label: 'Dashboard',
        url: 'https://grafana-dev-route-grafana-dev.apps.ocpitsd0001.xaas.epfl.ch/d/test-sa-dashboard/standard-namespace-monitoring-recording-rule?orgId=1&from=now-6h&to=now&timezone=browser&var-datasource=73a57e8b-7679-4a18-915c-292f143448c7&var-namespace=svc1751d-co2-calculator-dev&refresh=5m',
      },
      {
        label: 'Graphs',
        url: 'https://grafana-dev-route-grafana-dev.apps.ocpitsd0001.xaas.epfl.ch/d/ndr79mm/specific-graphs?orgId=1&from=now-12h&to=now&timezone=browser',
      },
    ],
    appLogs: [
      {
        label: 'Logs',
        url: 'https://console-openshift-console.apps.ocpitsd0001.xaas.epfl.ch/monitoring/logs?q=%7B+log_type%3D%22application%22+%7D+%7C+json',
      },
    ],
    platform: [
      {
        label: 'OpenShift',
        url: 'https://console-openshift-console.apps.ocpitsd0001.xaas.epfl.ch',
      },
    ],
  },
  {
    name: 'stage',
    gitops: [
      {
        label: 'GitOps (Tree)',
        url: 'https://openshift-gitops-server-openshift-gitops.apps.ocpitst0001.xaas.epfl.ch/applications/openshift-gitops/co2-calculator-stage?view=tree&resource=',
      },
      {
        label: 'GitOps (Home)',
        url: 'https://openshift-gitops-server-openshift-gitops.apps.ocpitst0001.xaas.epfl.ch/',
      },
    ],
    monitoring: [
      {
        label: 'Dashboard',
        url: 'https://grafana-test-route-grafana-test.apps.ocpitst0001.xaas.epfl.ch/d/k8s_views_ns/kubernetes-views-namespaces?orgId=1&from=now-1h&to=now&timezone=browser&var-datasource=73a57e8b-7679-4a18-915c-292f143448c7&var-cluster=&var-namespace=svc1751t-co2-calculator-stage&var-resolution=30s&var-created_by=$__all&refresh=30s',
      },
      {
        label: 'Graphs',
        url: 'https://grafana-test-route-grafana-test.apps.ocpitst0001.xaas.epfl.ch/d/ndr79mm/specific-graphs?orgId=1&from=now-12h&to=now&timezone=browser',
      },
    ],
    appLogs: [
      {
        label: 'Logs',
        url: 'https://console-openshift-console.apps.ocpitst0001.xaas.epfl.ch/monitoring/logs?q=%7B+log_type%3D%22application%22+%7D+%7C+json',
      },
    ],
    platform: [
      {
        label: 'OpenShift',
        url: 'https://console-openshift-console.apps.ocpitst0001.xaas.epfl.ch/',
      },
    ],
  },
  {
    name: 'prod',
    gitops: [
      {
        label: 'GitOps (Tree)',
        url: 'https://openshift-gitops-server-openshift-gitops.apps.ocpitsp0001.xaas.epfl.ch/applications/openshift-gitops/co2-calculator-prod?view=tree&resource=',
      },
      {
        label: 'GitOps (Home)',
        url: 'https://openshift-gitops-server-openshift-gitops.apps.ocpitsp0001.xaas.epfl.ch/',
      },
    ],
    monitoring: [
      {
        label: 'Dashboard',
        url: 'https://grafana-prod-route-grafana-prod.apps.ocpitsp0001.xaas.epfl.ch/d/k8s_views_ns/kubernetes-views-namespaces?orgId=1&from=now-1h&to=now&timezone=browser&var-datasource=73a57e8b-7679-4a18-915c-292f143448c7&var-cluster=&var-namespace=svc1751p-co2-calculator-prod&var-resolution=30s&var-created_by=$__all&refresh=30s',
      },
      {
        label: 'Graphs',
        url: 'https://grafana-prod-route-grafana-prod.apps.ocpitsp0001.xaas.epfl.ch/d/ndr79mm/specific-graphs?orgId=1&from=now-12h&to=now&timezone=browser',
      },
    ],
    appLogs: [
      {
        label: 'Logs',
        url: 'https://console-openshift-console.apps.ocpitsp0001.xaas.epfl.ch/monitoring/logs?q=%7B+log_type%3D%22application%22+%7D+%7C+json',
      },
    ],
    platform: [
      {
        label: 'OpenShift',
        url: 'https://console-openshift-console.apps.ocpitsp0001.xaas.epfl.ch/',
      },
    ],
  },
];
</script>

<template>
  <q-page>
    <navigation-header :item="SYSTEM_NAV.SYSTEM_LOGS" />
    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <div class="q-gutter-md">
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
