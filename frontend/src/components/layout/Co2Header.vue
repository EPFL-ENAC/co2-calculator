<script setup lang="ts">
import Co2LanguageSelector from 'src/components/atoms/Co2LanguageSelector.vue';
import { useAuthStore } from 'src/stores/auth';
import { useRouter } from 'vue-router';
import Co2Timeline from '../organisms/layout/Co2Timeline.vue';
import { useRoute } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const bottomToolbarVisible: Record<string, string> = {
  module: 'Module',
  results: 'Results',
  simulations: 'Simulations',
  'simulation-add': 'Simulation Add',
  'simulation-edit': 'Simulation Edit',
  documentation: 'Documentation',
  'backoffice-documentation': 'Backoffice Documentation',
  'system-documentation': 'System Documentation',
};

const handleLogout = async () => {
  await authStore.logout(router);
};
</script>

<template>
  <q-header class="bg-white text-dark">
    <!-- Top toolbar: Logo, Title, Language Selector -->
    <q-toolbar class="q-px-xl q-py-md">
      <q-toolbar-title class="row items-center no-wrap">
        <q-img src="/epfl-logo.svg" :alt="$t('logo-alt')" width="100px" />
        <span
          v-html="$t('calculator-title')"
          class="q-ml-md text-h3 text-weight-medium"
        >
        </span>
      </q-toolbar-title>

      <q-space />

      <Co2LanguageSelector />
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
    <template v-if="route.name && route.name in bottomToolbarVisible">
      <q-toolbar class="q-px-xl q-py-md items-center">
        <q-breadcrumbs class="text-grey-8">
          <q-breadcrumbs-el
            :label="$t('home')"
            :to="{ name: 'home', params: route.params }"
          />
          <q-breadcrumbs-el
            :label="
              route.params.module
                ? $t(route.params.module as string)
                : bottomToolbarVisible[route.name as string]
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
