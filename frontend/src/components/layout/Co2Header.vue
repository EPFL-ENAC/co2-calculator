<script setup lang="ts">
import Co2LanguageSelector from 'src/components/atoms/Co2LanguageSelector.vue';
import { useAuthStore } from 'src/stores/auth';
import { useRouter } from 'vue-router';
import Co2Timeline from '../organisms/layout/Co2Timeline.vue';
import { useRoute } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const getModuleLabel = () =>
  Array.isArray(route.params.module)
    ? (route.params.module[0] ?? '')
    : (route.params.module ?? '');

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
        <span class="q-ml-md text-h3 text-weight-medium">
          Calculator CO<sub>2</sub>
        </span>
      </q-toolbar-title>

      <q-space />

      <Co2LanguageSelector />
      <q-btn
        flat
        dense
        size="md"
        :label="$t('logout')"
        color="accent"
        class="q-ml-xl text-weight-medium"
        @click="handleLogout"
        no-caps
      />
    </q-toolbar>
    <q-separator />
    <!-- Bottom toolbar: Breadcrumbs and Action Button -->
    <template v-if="route.name === 'module' && route.matched.length > 2">
      <q-toolbar class="q-px-xl q-py-md items-center">
        <q-breadcrumbs class="text-grey-8">
          <q-breadcrumbs-el
            :label="$t('home')"
            :to="{
              name: 'home',
              params: {
                language: route.params.language || 'en',
                unit: route.params.unit,
                year: route.params.year,
              },
            }"
          />
          <q-breadcrumbs-el :label="$t(getModuleLabel())" />
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
