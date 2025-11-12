<script setup lang="ts">
import { computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { LOCALE_MAP, LANGUAGES } from 'src/constant/languages';

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();

const currentLanguage = computed(
  () => (route.params.language as string) || 'en',
);

const getRouteWithLanguage = (lang: string) => {
  return router.resolve({
    name: route.name,
    params: { ...route.params, language: lang },
    query: route.query,
  }).href;
};

watch(
  () => route.params.language,
  (lang) => {
    locale.value = LOCALE_MAP[lang as keyof typeof LOCALE_MAP] || LOCALE_MAP.en;
  },
  { immediate: true },
);
</script>

<template>
  <div class="language-selector q-gutter-x-xs">
    <template v-for="(lang, idx) in LANGUAGES" :key="lang">
      <router-link
        :to="getRouteWithLanguage(lang)"
        class="q-link--no-underline text-primary text-weight-medium text-body2"
        :class="{ 'text-decoration-underline': currentLanguage === lang }"
        >{{ lang.toUpperCase() }}</router-link
      >
      <span
        v-if="idx < LANGUAGES.length - 1"
        class="text-primary text-weight-medium text-body2"
        >/</span
      >
    </template>
  </div>
</template>
