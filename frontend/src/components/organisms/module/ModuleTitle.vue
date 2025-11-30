<template>
  <q-card flat class="container">
    <q-card-section>
      <h1 class="text-h2 q-mb-xs">
        <q-icon
          :name="MODULE_ICONS[type] ? MODULE_ICONS[type] : ''"
          color="accent"
          size="sm"
        ></q-icon>
        {{ $t(`${type}`) }}
      </h1>
      <p class="text-body1 q-mb-none">
        {{ $t(`${type}-description`) }}
      </p>
      <div class="absolute-top-right q-mr-md q-mt-md">
        <q-icon :name="outlinedInfo" size="md" class="cursor-pointer" />
        <!-- tooltip width should be token related -->
        <q-tooltip
          anchor="top right"
          self="bottom right"
          class="u-tooltip-max-width"
        >
          {{ $t(`${type}-title-tooltip`) }}
        </q-tooltip>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { MODULE_ICONS } from 'src/constant/moduleCards';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { Module } from 'src/constant/modules';

defineProps<{
  type: Module;
}>();
</script>
