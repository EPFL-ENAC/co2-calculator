<script setup lang="ts">
import { computed } from 'vue';

type ButtonColor = 'primary' | 'secondary';
type ButtonSize = 'xs' | 'sm' | 'md';

const props = withDefaults(
  defineProps<{
    label: string;
    color?: ButtonColor;
    size?: ButtonSize;
    disabled?: boolean;
    fullwidth?: boolean;
    handleClick?: (event: MouseEvent) => void;
    htmlType?: 'button' | 'submit' | 'reset';
  }>(),
  {
    color: 'primary',
    size: 'md',
    disabled: false,
    fullwidth: false,
    htmlType: 'button',
  },
);

const buttonClasses = computed(() => {
  const classes = ['text-weight-medium'];
  if (props.color) {
    classes.push(`button-${props.color}`);
  }

  if (props.disabled) {
    classes.push('button-disabled');
  }

  if (props.size) {
    classes.push(`button-${props.size}`);
  }

  if (props.fullwidth) {
    classes.push('full-width');
  }
  return classes;
});
</script>

<template>
  <q-btn
    :type="htmlType"
    no-caps
    full-width
    :disable="disabled"
    :label="label"
    :class="buttonClasses"
    @click="handleClick || undefined"
  />
</template>
