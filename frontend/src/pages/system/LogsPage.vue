<script setup lang="ts">
import { SYSTEM_NAV } from 'src/constant/sidebarNavigation';
</script>

<template>
  <q-page>
    <div class="q-my-xl q-px-xl">
      <div class="flex items-center q-gutter-md">
        <q-icon :name="SYSTEM_NAV.SYSTEM_LOGS.icon" size="sm" color="accent" />
        <h1 class="text-h3 text-weight-bold">
          {{ $t(SYSTEM_NAV.SYSTEM_LOGS.routeName) }}
        </h1>
      </div>
      <p class="text-body1 text-secondary">
        {{ $t(SYSTEM_NAV.SYSTEM_LOGS.description) }}
      </p>
    </div>
    <q-separator />
    <div class="q-my-xl q-px-xl">
      <div class="container">
        <p class="text-h1">Placeholder: Add Grafana iFrame</p>
      </div>
    </div>
  </q-page>
</template>
