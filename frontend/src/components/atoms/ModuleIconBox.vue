<script setup lang="ts">
import { computed } from 'vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import {
  getModuleIconColors,
  makeBoxBackground,
} from 'src/composables/useModuleIconColors';

const props = withDefaults(
  defineProps<{
    name: string;
    size?: 'sm' | 'md' | 'lg';
  }>(),
  { size: 'md' },
);

const colors = computed(() => getModuleIconColors(props.name));
</script>

<template>
  <span
    class="module-icon-box"
    :class="`module-icon-box--${size}`"
    :style="{
      color: colors.buttonTextColor,
      background: makeBoxBackground(colors.bgColor, colors.buttonTextColor),
    }"
  >
    <ModuleIcon :name="name" color="" size="md" />
  </span>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-icon-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: tokens.$module-icon-box-border-radius;
  border: tokens.$module-icon-box-border-width solid transparent;
  flex-shrink: 0;

  &--sm {
    width: tokens.$module-icon-box-size-sm;
    height: tokens.$module-icon-box-size-sm;
  }

  &--md {
    width: tokens.$module-icon-box-size-md;
    height: tokens.$module-icon-box-size-md;
  }

  &--lg {
    width: tokens.$module-icon-box-size-lg;
    height: tokens.$module-icon-box-size-lg;
  }
}
</style>
