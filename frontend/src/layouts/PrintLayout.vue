<template>
  <q-layout view="lHh Lpr lFf" class="print-layout">
    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { providePrintMode } from 'src/composables/print/usePrintMode';

providePrintMode(true);
</script>

<style>
@page {
  size: A4 portrait;
  margin: 0;
}

body {
  background: white;
}

@media print {
  body {
    background: white !important;
  }

  /* Quasar sizes QLayout to 100vh and adds inline offset padding to
     QPageContainer for the (now hidden) header/footer. Left as-is, that
     overflows the content onto a trailing blank sheet. */
  .q-layout,
  .q-page-container {
    min-height: 0 !important;
  }

  .q-page-container {
    padding: 0 !important;
  }
}
</style>

<style scoped>
.print-layout {
  background: white;
}
</style>
