<script setup lang="ts">
import { computed } from 'vue';
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
</script>

<template>
  <div class="language-selector">
    <router-link
      :to="englishRoute"
      class="text-primary text-weight-medium text-body1 no-underline"
      :class="{ 'text-decoration-underline': isEnglish }"
      @click="switchLanguage('en')"
      aria-label="Switch to English"
    >
      EN
    </router-link>
    <span class="text-primary text-weight-medium text-body1">/</span>
    <router-link
      :to="frenchRoute"
      class="text-primary text-weight-medium text-body1 no-underline"
      :class="{ 'text-decoration-underline': isFrench }"
      @click="switchLanguage('fr')"
      aria-label="Switch to French"
    >
      FR
    </router-link>
  </div>
</template>
