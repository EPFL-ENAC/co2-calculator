<script setup lang="ts">
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/NavigationHeader.vue';
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT" />
  </q-page>
</template>
