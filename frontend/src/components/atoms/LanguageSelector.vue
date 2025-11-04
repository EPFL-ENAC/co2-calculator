<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const { locale } = useI18n();

const isEnglish = computed(() => locale.value === 'en-US');
const isFrench = computed(() => locale.value === 'fr-CH');

const switchToEnglish = () => {
  locale.value = 'en-US';
};

const switchToFrench = () => {
  locale.value = 'fr-CH';
};
</script>

<template>
  <div class="language-selector">
    <button
      class="language-selector__option"
      :class="{ 'language-selector__option--active': isEnglish }"
      @click="switchToEnglish"
      type="button"
      aria-label="Switch to English"
    >
      EN
    </button>
    <span class="language-selector__separator">/</span>
    <button
      class="language-selector__option"
      :class="{ 'language-selector__option--active': isFrench }"
      @click="switchToFrench"
      type="button"
      aria-label="Switch to French"
    >
      FR
    </button>
  </div>
</template>
