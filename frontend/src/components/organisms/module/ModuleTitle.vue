<template>
  <q-card flat class="module-title-card relative container">
    <q-card-section>
      <div class="row justify-between">
        <div class="flex items-center q-mb-xs">
          <module-icon
            v-if="type"
            :name="type"
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
          v-if="hasTooltip"
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer"
          :aria-label="$t('module-info-label')"
        />
      </div>

      <p v-if="hasDescription" class="text-body2 q-mb-none">
        {{ $t(`${type}-description`) }}
      </p>
      <div
        v-if="hasDescriptionSubtext"
        class="text-caption text-grey-6 q-mt-sm q-mb-none"
      >
        {{ $t(`${type}-title-subtext`) }}
      </div>
      <q-tooltip
        v-if="hasTooltip"
        anchor="center right"
        self="top right"
        class="u-tooltip"
      >
        <div class="text-h5 text-weight-medium q-mb-sm">
          {{ $t(`${type}-title-tooltip-title`) }}
        </div>
        <p v-if="hasTooltipSubText">
          {{ $t(`${type}-title-tooltip-subtext`) }}
        </p>
      </q-tooltip>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { Module } from 'src/constant/modules';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

/*
i18n keys used in this component:
- module-info-label
- {module-type}
- {module-type}-description
- {module-type}-subtext
- {module-type}-title-tooltip-title
- {module-type}-title-subtext
*/

withDefaults(
  defineProps<{
    type: Module;
    hasTooltip?: boolean;
    hasDescription?: boolean;
    hasDescriptionSubtext?: boolean;
    hasTooltipSubText?: boolean;
  }>(),
  {
    hasTooltip: true,
    hasDescription: false,
    hasDescriptionSubtext: false,
    hasTooltipSubText: false,
  },
);
</script>
<style scoped lang="scss">
.module-title-card {
  height: 100%;
}
</style>
