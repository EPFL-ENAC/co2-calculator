<script setup lang="ts">
import { SYSTEM_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
</script>

<template>
  <q-page>
    <navigation-header :item="SYSTEM_NAV.SYSTEM_USER_MANAGEMENT" />

    <div class="q-my-xl q-px-xl">
      <div class="container">
        <p class="text-h1">Placeholder: Redirect to Accred</p>
      </div>
    </div>
  </q-page>
</template>
