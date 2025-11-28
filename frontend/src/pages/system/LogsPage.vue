<script setup lang="ts">
import { SYSTEM_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/NavigationHeader.vue';
</script>

<template>
  <q-page>
    <navigation-header :item="SYSTEM_NAV.SYSTEM_LOGS" />

    <div class="q-my-xl q-px-xl">
      <div class="container">
        <p class="text-h1">Placeholder: Add Grafana iFrame</p>
      </div>
    </div>
  </q-page>
</template>
