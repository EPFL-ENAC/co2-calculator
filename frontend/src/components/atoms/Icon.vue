<script setup lang="ts">
import { computed } from 'vue';

type IconSize = 'sm' | 'md' | 'lg' | 'xl';
type IconColor = 'grey' | 'red' | 'black' | 'white' | 'disabled';

const props = withDefaults(
  defineProps<{
    name: string;
    color?: IconColor;
    size?: IconSize;
  }>(),
  {
    color: 'grey',
    size: 'md',
  },
);

const outlinedIconName = computed(() => {
  // Material Symbols (webfont) requires sym_o_ prefix for outlined icons
  return `sym_o_${props.name}`;
});

const iconClasses = computed(() => {
  return ['icon', `icon--${props.color}`, `icon--${props.size}`];
});
</script>

<template>
  <q-icon :name="outlinedIconName" size="xs" :class="iconClasses" />
</template>
