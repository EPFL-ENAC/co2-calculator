<script setup lang="ts">
import Co2LanguageSelector from 'src/components/atoms/Co2LanguageSelector.vue';
import { useAuthStore } from 'src/stores/auth';
import { useRouter } from 'vue-router';
import Co2Timeline from '../organisms/layout/Co2Timeline.vue';
import { useRoute } from 'vue-router';
import { timelineItems } from 'app/constant/timelineItems';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const getModuleLabel = (module: string | string[] | undefined) => {
  const key = Array.isArray(module) ? module[0] : module;
  if (!key) return '';
  const item = timelineItems.find((item) => item.link === key);
  return item ? item.label : key;
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
        <q-img src="/epfl-logo.svg" :alt="$t('logo_alt')" width="100px" />
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
        label="logout"
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
            label="Home"
            :to="{
              name: 'home',
              params: {
                language: route.params.language || 'en',
                unit: route.params.unit,
                year: route.params.year,
              },
            }"
          />
          <q-breadcrumbs-el :label="$t(getModuleLabel(route.params.module))" />
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
      <div class="flex justify-center q-py-xl items-center">
        <Co2Timeline />
      </div>
      <q-separator />
    </template>
  </q-header>
</template>
