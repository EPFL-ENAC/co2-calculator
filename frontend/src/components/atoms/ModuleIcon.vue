<script setup lang="ts">
import { computed } from 'vue';
import { icons } from 'src/plugin/module-icon';

const props = defineProps<{
  name: string;
  size?: 'sm' | 'md' | 'lg';
  color?: string;
}>();

const svg = computed(() => icons[props.name] || '');
</script>

<template>
  <span
    class="module-icon"
    :class="[size ? `module-icon--${size}` : '', color ? `text-${color}` : '']"
    v-html="svg"
  />
</template>
