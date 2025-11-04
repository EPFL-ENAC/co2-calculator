<script setup lang="ts">
import { computed } from 'vue';
import Icon from 'src/components/atoms/Icon.vue';

type ButtonType = 'primary' | 'secondary' | 'disabled';
type ButtonSize = 'xs' | 'sm' | 'md';

const props = withDefaults(
  defineProps<{
    icon?: string;
    type?: ButtonType;
    size?: ButtonSize;
    disabled?: boolean;
    fullwidth?: boolean;
    onClick?: (event: MouseEvent) => void;
    htmlType?: 'button' | 'submit' | 'reset';
  }>(),
  {
    type: 'primary',
    size: 'md',
    disabled: false,
    fullwidth: false,
    onClick: undefined,
    htmlType: 'button',
  },
);

const buttonClasses = computed(() => {
  const classes = ['button', `button--${props.type}`, `button--${props.size}`];
  if (props.fullwidth) {
    classes.push('button--fullwidth');
  }
  return classes;
});

const isDisabled = computed(() => {
  return props.disabled || props.type === 'disabled';
});

const iconSize = computed(() => {
  // Map ButtonSize to IconSize
  // ButtonSize: 'xs' | 'sm' | 'md'
  // IconSize: 'sm' | 'md' | 'lg' | 'xl'
  const sizeMap: Record<ButtonSize, 'sm' | 'md'> = {
    xs: 'sm',
    sm: 'sm',
    md: 'md',
  };
  return sizeMap[props.size];
});

const handleClick = (event: MouseEvent) => {
  if (!isDisabled.value && props.onClick) {
    props.onClick(event);
  }
};
</script>

<template>
  <button
    :type="htmlType"
    :class="buttonClasses"
    :disabled="isDisabled"
    @click="handleClick"
  >
    <Icon v-if="icon" :name="icon" :size="iconSize" color="grey" />
    <slot />
  </button>
</template>
