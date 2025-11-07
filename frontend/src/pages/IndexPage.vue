<template>
  <q-page class="row items-center justify-evenly">
    <q-input v-model="title" label="Standard" />
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const title = ref<string>('Index Page');
</script>
