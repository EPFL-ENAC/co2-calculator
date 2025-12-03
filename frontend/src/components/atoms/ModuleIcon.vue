<script setup lang="ts">
import { ref, computed, watchEffect } from 'vue';
import { icons } from 'src/plugin/module-icon';

const props = withDefaults(
  defineProps<{
    name: string;
    size?: 'sm' | 'md' | 'lg';
    color?: string; // e.g., 'primary', 'accent', 'grey-8';
  }>(),
  {
    size: 'md',
    color: 'accent',
  },
);

const iconRef = ref<HTMLElement>();
const svgContent = computed(() => icons[props.name] || '');

watchEffect(
  () => {
    if (iconRef.value && svgContent.value) {
      iconRef.value.innerHTML = svgContent.value;
    }
  },
  { flush: 'post' },
);

const iconClass = computed(() => [
  'module-icon',
  `module-icon--${props.size}`,
  props.color ? `text-${props.color}` : '',
]);
</script>

<template>
  <span ref="iconRef" :class="iconClass" />
</template>
