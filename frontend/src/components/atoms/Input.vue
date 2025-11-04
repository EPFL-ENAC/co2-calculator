<script lang="ts" setup>
import { computed } from 'vue';

type InputType = 'text' | 'password' | 'date' | 'email' | 'number';

interface Props {
  modelValue?: string;
  placeholder?: string;
  icon?: string;
  disabled?: boolean;
  size?: 'md' | 'lg';
  type?: InputType;
  error?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: undefined,
  icon: '',
  modelValue: '',
  disabled: false,
  size: 'md',
  type: 'text',
  error: false,
});

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const value = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v),
});

const showIcon = computed(() => !!props.icon);
const iconIsUrl = computed(
  () => !!props.icon && /^(data:|https?:\/\/|\/|\.)/.test(props.icon),
);

const wrapperClasses = computed(() => {
  const classes = ['input-wrapper'];

  // Size modifier
  classes.push(`input-wrapper--${props.size}`);

  // Conditional classes
  if (props.disabled) classes.push('disabled');
  if (showIcon.value) classes.push('has-icon');
  if (props.error) classes.push('input-wrapper--error');

  return classes;
});
</script>

<template>
  <div :class="wrapperClasses" role="group" :aria-disabled="disabled">
    <span v-if="showIcon" class="input-icon" aria-hidden="true">
      <img v-if="iconIsUrl" :src="icon" alt="" />
      <i v-else :class="icon" aria-hidden="true"></i>
    </span>

    <input
      v-model="value"
      :type="type"
      :placeholder="placeholder"
      :disabled="disabled"
      class="input-field"
    />
  </div>
</template>
