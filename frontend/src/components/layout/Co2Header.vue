<script setup lang="ts">
import { computed } from 'vue';
import Co2LanguageSelector from 'src/components/atoms/Co2LanguageSelector.vue';
import { useAuthStore } from 'src/stores/auth';
import { useRouter } from 'vue-router';
import Co2Timeline from '../organisms/layout/Co2Timeline.vue';
import { useRoute } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

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

const handleLogout = async () => {
  await authStore.logout(router);
};
</script>

<template>
  <q-header class="bg-white text-dark">
    <!-- Top toolbar: Logo, Title, Language Selector -->
    <q-toolbar class="q-px-xl q-py-md">
      <q-toolbar-title class="row items-center no-wrap">
        <q-img src="/epfl-logo.svg" :alt="$t('logo_alt')" width="100px" />
        <span
          v-html="$t('calculator_title')"
          class="q-ml-md text-h3 text-weight-medium"
        >
        </span>
      </q-toolbar-title>

      <q-space />

      <Co2LanguageSelector />

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
            params: { language: route.params.language || 'en' },
          }"
        />
      </template>

      <q-btn
        flat
        dense
        no-caps
        size="md"
        color="accent"
        :label="$t('logout')"
        class="q-ml-xl text-weight-medium"
        @click="handleLogout"
      />
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
          color="red"
          label="Fake Button"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
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
