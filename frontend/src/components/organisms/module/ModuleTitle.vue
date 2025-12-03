<template>
  <q-card flat class="module-title-card relative container">
    <q-card-section>
      <div class="row justify-between">
        <div class="flex items-center q-mb-xs">
          <module-icon
            v-if="iconName"
            :name="iconName"
            color="accent"
            size="md"
            class="q-mr-sm"
            :aria-label="$t('module-info-label')"
          ></module-icon>
          <span class="text-h3 text-weight-medium q-mb-none">{{
            $t(`${type}`)
          }}</span>
        </div>
        <q-icon
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer"
          :aria-label="$t('module-info-label')"
        />
        <!-- tooltip width should be token related -->
      </div>

      <p class="text-body2 q-mb-none">
        {{ $t(`${type}-description`) }}
      </p>
      <div class="absolute-top-right q-mr-md q-mt-md"></div>
      <q-tooltip
        anchor="top right"
        self="bottom right"
        class="u-tooltip-max-width"
      >
        {{ $t(`${type}-title-tooltip`) }}
      </q-tooltip>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { MODULE_ICONS } from 'src/constant/moduleCards';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { Module } from 'src/constant/modules';
import { computed } from 'vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

const props = defineProps<{
  type: Module;
}>();
const iconName = computed(() => MODULE_ICONS[props.type] || null);
</script>
<style scoped lang="scss">
.module-title-card {
  height: 100%;
}
</style>
