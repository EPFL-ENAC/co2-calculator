<script setup lang="ts">
import { computed } from 'vue';
import Co2LanguageSelector from 'src/components/atoms/Co2LanguageSelector.vue';
import { useAuthStore } from 'src/stores/auth';
import { useRouter } from 'vue-router';
import Co2Timeline from '../organisms/layout/Co2Timeline.vue';
import { useRoute } from 'vue-router';
import { useTimelineStore } from 'src/stores/modules';
import { Module } from 'src/constant/modules';
import { useI18n } from 'vue-i18n';
import { ROLES } from 'src/constant/roles';
import { isBackOfficeRoute } from 'src/router/routes';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const timelineStore = useTimelineStore();
const { t } = useI18n();

const unitName = computed(() => {
  if (!route.params.unit) return '';
  return decodeURIComponent(route.params.unit as string);
});

const year = computed(() => {
  return route.params.year || '';
});

const workspaceDisplay = computed(() => {
  if (!unitName.value || !year.value) return '';
  return `${unitName.value} | ${year.value}`;
});

const currentModule = computed(() => route.params.module as string | undefined);
const currentState = computed(() => {
  if (!currentModule.value) return null;
  return timelineStore.itemStates[currentModule.value];
});
const toggleLabel = computed(() =>
  currentState.value === 'validated'
    ? t('common_unvalidate')
    : t('common_validate'),
);
const toggleColor = computed(() =>
  currentState.value === 'validated' ? 'primary' : 'info',
);

function toggleState() {
  if (!currentModule.value) return;
  const newState =
    currentState.value === 'validated' ? 'in-progress' : 'validated';
  timelineStore.setState(currentModule.value as Module, newState);
}

const handleLogout = async () => {
  await authStore.logout(router);
};

const hasBackOfficeAccess = computed(() => {
  console.log(authStore.user);
  if (!authStore.user) return false;
  const userRoles = authStore.user.roles.map((r) => r.role);
  return (
    userRoles.includes(ROLES.BackOfficeAdmin) ||
    userRoles.includes(ROLES.BackOfficeStandard)
  );
});

const isInBackOfficeRoute = computed(() => isBackOfficeRoute(route));
</script>

<template>
  <q-header class="bg-white text-dark">
    <!-- Top toolbar: Logo, Title, Language Selector -->
    <q-toolbar class="q-px-xl q-py-md">
      <q-toolbar-title class="row items-center no-wrap">
        <q-img src="/epfl-logo.svg" :alt="$t('logo_alt')" width="100px" />
        <span class="q-ml-md text-h3 text-weight-medium">{{
          $t('calculator_title')
        }}</span>
      </q-toolbar-title>

      <q-space />

      <Co2LanguageSelector />

      <q-btn
        icon="o_article"
        color="grey-4"
        text-color="primary"
        :label="$t('documentation_button_label')"
        unelevated
        no-caps
        outline
        size="sm"
        class="text-weight-medium q-ml-xl"
        :to="{ name: 'back-office-documentation' }"
      />

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
          name: 'workspace-setup',
          params: {
            language: route.params.language || 'en',
          },
        }"
      />

      <template v-if="route.name !== 'workspace-setup'">
        <span
          v-if="workspaceDisplay"
          class="text-body2 text-weight-medium q-ml-xl q-mr-sm"
        >
          {{ workspaceDisplay }}
        </span>

        <q-btn
          icon="o_autorenew"
          :label="$t('workspace_change_btn')"
          unelevated
          no-caps
          size="sm"
          class="text-weight-medium btn-secondary"
          :to="{
            name: 'workspace-setup',
            params: {
              language: route.params.language || 'en',
            },
            query: {
              unit: null,
              year: null,
            },
          }"
        />
      </template>

      <q-btn-dropdown
        flat
        dense
        no-caps
        color="accent"
        size="md"
        :label="authStore.displayName"
        class="q-ml-xl text-weight-medium"
      >
        <q-list>
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
          <q-breadcrumbs-el
            class="text-capitalize"
            :label="
              route.params.module
                ? $t(route.params.module as string)
                : $t(route.name as string)
            "
          />
        </q-breadcrumbs>

        <q-space />

        <q-btn
          v-if="route.name === 'module'"
          :outline="currentState === 'validated' ? true : false"
          :label="toggleLabel"
          :color="toggleColor"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          @click="toggleState"
        />
      </q-toolbar>
      <q-separator />
    </template>
    <template v-if="route.name === 'module'">
      <Co2Timeline />
      <q-separator />
    </template>
  </q-header>
</template>
