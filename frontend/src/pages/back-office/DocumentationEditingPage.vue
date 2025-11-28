<script setup lang="ts">
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
</script>

<template>
  <q-page>
    <navigation-header
      :item="BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING"
    />
  </q-page>
</template>
