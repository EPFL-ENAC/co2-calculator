<script setup lang="ts">
import { useRoute } from 'vue-router';
import { LANGUAGES } from 'src/constant/languages';

const route = useRoute();
</script>

<template>
  <div class="language-selector">
    <router-link
      v-for="lang in LANGUAGES"
      :key="lang"
      :to="{
        name: route.name,
        params: { ...route.params, language: lang },
        query: route.query,
      }"
      class="language-link text-primary text-weight-medium text-body2"
    >
      <span class="language-text text-uppercase">{{ lang }}</span>
    </router-link>
  </div>
</template>
<style scoped lang="scss">
.language-link {
  text-decoration: none;

  &.router-link-active .language-text {
    text-decoration: underline;
  }

  &:not(:last-child)::after {
    content: ' / ';
  }
}
</style>
