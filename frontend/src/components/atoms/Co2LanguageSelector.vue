<script setup lang="ts">
import { computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';

const route = useRoute();
const { locale } = useI18n();

const isEnglish = computed(() => locale.value === 'en-US');
const isFrench = computed(() => locale.value === 'fr-CH');

// Generate route with switched language
const getRouteWithLanguage = (newLanguage: 'en' | 'fr') => {
  const currentPath = route.path;
  const pathParts = currentPath.split('/').filter(Boolean);

  // Check if first part is a language code
  if (
    pathParts.length > 0 &&
    (pathParts[0] === 'en' || pathParts[0] === 'fr')
  ) {
    // Replace the language code
    pathParts[0] = newLanguage;
    return '/' + pathParts.join('/');
  }

  // No language in path, add it
  return `/${newLanguage}${currentPath}`;
};

const englishRoute = computed(() => getRouteWithLanguage('en'));
const frenchRoute = computed(() => getRouteWithLanguage('fr'));

// Update locale when language changes
const switchLanguage = (lang: 'en' | 'fr') => {
  locale.value = lang === 'en' ? 'en-US' : 'fr-CH';
};

// Watch for route language changes and update i18n locale
watch(
  () => route.params.language,
  (newLang) => {
    if (newLang === 'en') {
      locale.value = 'en-US';
    } else if (newLang === 'fr') {
      locale.value = 'fr-CH';
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="language-selector q-gutter-x-xs">
    <router-link
      :to="englishRoute"
      class="q-link--no-underline text-primary text-weight-medium text-body2"
      :style="{ textDecoration: !isEnglish ? 'none' : 'underline' }"
      @click="switchLanguage('en')"
      >EN</router-link
    >
    <span class="text-primary text-weight-medium text-body2">/</span>
    <router-link
      :to="frenchRoute"
      class="q-link--no-underline text-primary text-weight-medium text-body2"
      :style="{ textDecoration: !isFrench ? 'none' : 'underline' }"
      @click="switchLanguage('fr')"
      >FR</router-link
    >
  </div>
</template>
