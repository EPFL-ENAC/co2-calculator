<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Co2LanguageSelector from 'src/components/atoms/Co2LanguageSelector.vue';
import { useAuthStore } from 'src/stores/auth';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useColorblindStore } from 'src/stores/colorblind';
import { useRouter } from 'vue-router';
import { useRoute } from 'vue-router';
import { isBackOfficeRoute, DEFAULT_ROUTE_NAME } from 'src/router/routes';
import { PermissionAction } from 'src/stores/auth';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const workspaceStore = useWorkspaceStore();
const colorblindStore = useColorblindStore();
const { t } = useI18n();

const unitName = computed(() => {
  return workspaceStore.selectedUnit?.name || '';
});

const year = computed(() => {
  return workspaceStore.selectedYear || '';
});

const simulationContext = computed(() => {
  if (route.name === 'simulation-explore') return 'explore';
  if (route.name === 'simulation-plan') return 'plan';
  return null;
});

const workspaceDisplay = computed(() => {
  if (!unitName.value || !year.value) return '';
  if (simulationContextLabel.value) {
    return `${unitName.value} | ${t(simulationContextLabel.value)}`;
  }
  return `${unitName.value} | ${year.value}`;
});

const simulationContextLabel = computed(() => {
  if (simulationContext.value === 'explore') return 'simulation_tab_explore';
  if (simulationContext.value === 'plan') return 'simulation_tab_plan';
  return null;
});

const handleLogout = async () => {
  await authStore.logout(router);
};

const hasBackOfficeAccess = computed(() => {
  return authStore.hasUserBackOfficeAreaPermission(PermissionAction.VIEW);
});

const isInBackOfficeRoute = computed(() => isBackOfficeRoute(route));

const breadcrumbLabel = computed(() =>
  route.params.module
    ? t(route.params.module as string)
    : t(route.name as string),
);

const logoRoute = computed(() => {
  // Inside a workspace (unit + year present) the logo returns to the unified
  // home page; otherwise it falls back to the landing resolver.
  if (route.params.unit && route.params.year) {
    return {
      name: 'home',
      params: {
        language: route.params.language || 'en',
        unit: route.params.unit,
        year: route.params.year,
      },
    };
  }

  return {
    name: DEFAULT_ROUTE_NAME,
    params: {
      language: route.params.language || 'en',
    },
  };
});
</script>

<template>
  <q-header class="bg-white text-dark">
    <!-- Top toolbar: Logo, Title, Language Selector -->
    <q-toolbar class="q-px-xl q-py-md">
      <q-toolbar-title class="row items-center no-wrap">
        <router-link
          :to="logoRoute"
          :aria-label="$t('home')"
          :title="$t('home')"
          class="toolbar-home-link row items-center no-wrap"
        >
          <q-img src="/epfl-logo.svg" :alt="$t('logo_alt')" width="100px" />
          <span class="q-ml-md text-h3 text-weight-medium">{{
            $t('calculator_title')
          }}</span>
        </router-link>
      </q-toolbar-title>

      <q-space />

      <Co2LanguageSelector />

      <q-btn
        v-if="hasBackOfficeAccess && !isInBackOfficeRoute"
        color="grey-4"
        text-color="primary"
        :label="$t('user_management_access_button')"
        unelevated
        no-caps
        outline
        size="sm"
        class="text-weight-medium q-ml-xl"
        :to="{ name: 'back-office' }"
      />
      <q-btn
        v-if="hasBackOfficeAccess && isInBackOfficeRoute"
        color="grey-4"
        text-color="primary"
        :label="$t('back_to_calculator_button')"
        unelevated
        no-caps
        outline
        size="sm"
        class="text-weight-medium q-ml-xl"
        :to="{
          name: DEFAULT_ROUTE_NAME,
          params: {
            language: route.params.language || 'en',
          },
        }"
      />

      <!-- The unified home page hosts the Unit/Year dropdowns itself, so the
           workspace summary + "Change workspace" shortcut are suppressed there
           and only shown on the module / results / simulation routes. -->
      <template v-if="route.name !== 'home'">
        <span
          v-if="workspaceDisplay"
          class="text-body2 text-weight-medium q-ml-xl q-mr-sm"
        >
          {{ workspaceDisplay }}
        </span>

        <q-btn
          icon="o_autorenew"
          color="grey-4"
          text-color="primary"
          :label="$t('workspace_change_btn')"
          unelevated
          no-caps
          outline
          size="sm"
          class="text-weight-medium q-ml-xl"
          :to="{
            name: 'home',
            params: {
              language: route.params.language || 'en',
              unit: route.params.unit,
              year: route.params.year,
            },
          }"
        />
      </template>

      <q-btn-dropdown
        flat
        dense
        no-caps
        outline
        color="accent"
        size="md"
        :label="authStore.displayName"
        class="q-ml-xl text-weight-medium"
      >
        <q-list>
          <q-item>
            <q-item-section>
              <q-toggle
                :model-value="colorblindStore.enabled"
                :label="$t('results_colorblind_mode')"
                color="accent"
                keep-color
                size="md"
                class="text-weight-medium"
                @update:model-value="colorblindStore.setEnabled"
              />
            </q-item-section>
          </q-item>
          <q-separator />
          <q-item clickable @click="handleLogout">
            <q-item-section>
              <q-item-label>{{ $t('logout') }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-btn-dropdown>
    </q-toolbar>
    <q-separator />
    <!-- Bottom toolbar: Breadcrumbs and Action Button -->
    <template v-if="route.meta.breadcrumb">
      <q-toolbar class="q-px-xl q-py-md items-center">
        <q-breadcrumbs class="text-grey-8">
          <q-breadcrumbs-el
            :label="$t('home')"
            :to="{ name: 'home', params: route.params }"
          />
          <q-breadcrumbs-el class="text-capitalize" :label="breadcrumbLabel" />
        </q-breadcrumbs>
      </q-toolbar>
      <q-separator />
    </template>
  </q-header>
</template>
<style scoped>
.toolbar-home-link {
  text-decoration: none;
  color: inherit;
}
</style>
