<script setup lang="ts">
import LoginCard from 'src/components/organisms/login/LoginCard.vue';
</script>

<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container>
      <q-page class="login-page row items-center justify-evenly">
        <login-card></login-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>
