<template>
  <q-card flat class="module-title-card relative container">
    <q-card-section>
      <div class="row justify-between items-start">
        <div class="title-group">
          <div class="title-row">
            <ModuleIconBox v-if="type" :name="type" size="sm" />
            <h1 class="text-h3 text-weight-medium q-mb-none">
              {{ $t(`${type}`) }}
            </h1>
          </div>
          <p
            v-if="hasDescription"
            class="text-body1 text-grey-7 q-mb-none q-mt-sm"
          >
            {{ $t(`${type}-description`) }}
          </p>
          <p
            v-if="hasDescriptionSubtext"
            class="text-caption text-grey-5 q-mb-none q-mt-xs"
          >
            {{ $t(`${type}-title-subtext`) }}
          </p>
        </div>
        <q-icon
          v-if="hasTooltip"
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer"
          :aria-label="$t('module-info-label')"
        >
          <q-tooltip anchor="center right" self="top right" class="u-tooltip">
            <p v-if="hasTooltipSubText">
              {{ $t(`${type}-title-tooltip-subtext`) }}
            </p>
          </q-tooltip>
        </q-icon>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { Module } from 'src/constant/modules';
import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';

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
@use 'src/css/02-tokens' as tokens;

.module-title-card {
  height: 100%;
}

.title-group {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-md;
}
</style>
