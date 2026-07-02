<script setup lang="ts">
import LoginCard from 'src/components/organisms/login/LoginCard.vue';
</script>

<template>
  <q-page class="login-page row items-center justify-evenly">
    <login-card></login-card>
  </q-page>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.login-page {
  position: relative;
  min-height: tokens.$login-page-height;
  width: tokens.$login-page-width;

  &::before {
    content: '';
    position: absolute;
    width: tokens.$login-page-width;
    height: tokens.$login-page-height;
    background-image: url('/login-img.svg');
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
    background-color: rgba(
      tokens.$login-page-bg-color,
      tokens.$login-page-bg-opacity
    );
    z-index: tokens.$login-page-bg-blur-z-index;
  }
}
</style>
