<script setup lang="ts">
import LoginCard from '@/components/organisms/login/LoginCard.vue';
</script>

<template>
  <q-page class="login-page row items-center justify-evenly">
    <login-card mode="test"></login-card>
  </q-page>
</template>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

.login-page {
  position: relative;
  min-height: tokens.$login-page-height;
  width: tokens.$login-page-width;

  &::before {
    content: '';
    position: absolute;
    width: tokens.$login-page-width;
    height: tokens.$login-page-height;
    background-image: url('/institution/login-illustration.svg');
    background-size: auto;
    background-position: center;
    background-repeat: repeat;
    filter: blur(tokens.$login-page-bg-blur);
    z-index: tokens.$login-page-bg-z-index;
  }

  &::after {
    content: '';
    position: absolute;
    width: tokens.$login-page-width;
    height: tokens.$login-page-height;
    // A theme token is a CSS variable, so Sass rgba() cannot fade it (#500).
    background-color: color-mix(
      in srgb,
      #{tokens.$login-page-bg-color}
        #{percentage(tokens.$login-page-bg-opacity)},
      transparent
    );
    z-index: tokens.$login-page-bg-blur-z-index;
  }
}
</style>
