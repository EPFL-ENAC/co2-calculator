<script lang="ts" setup>
import { computed } from 'vue';

type InputType = 'text' | 'password' | 'date' | 'email' | 'number';

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    placeholder?: boolean | string;
    icon?: string;
    disabled?: boolean | string;
    size?: 'md' | 'lg';
    type?: InputType;
    error?: boolean;
  }>(),
  {
    placeholder: false,
    icon: '',
    modelValue: '',
    disabled: false,
    size: 'md',
    type: 'text',
    error: false,
  },
);

const emit = defineEmits<(e: 'update:modelValue', value: string) => void>();

// Input value
const value = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v),
});

// Show icon if icon is not empty
const showIcon = computed(() => !!props.icon);
const iconIsUrl = computed(
  () => !!props.icon && /^(data:|https?:\/\/|\/|\.)/.test(props.icon),
);

// Normalize disabled
const isDisabled = computed(() => {
  if (props.disabled === true) return true;
  if (props.disabled === false || props.disabled == null) return false;
  const s = String(props.disabled).toLowerCase();
  if (s === '') return true;
  if (s === 'true') return true;
  if (s === 'false') return false;
  return Boolean(s);
});

// Normalize placeholder - handle boolean for "Item Description" default
const placeholderText = computed(() => {
  if (props.placeholder === true || props.placeholder === '') {
    return 'Item Description';
  }
  if (props.placeholder === false || props.placeholder == null) {
    return '';
  }
  return String(props.placeholder);
});

const showPlaceholder = computed(() => {
  return (
    props.placeholder === true ||
    props.placeholder === '' ||
    (typeof props.placeholder === 'string' && props.placeholder.length > 0)
  );
});

const wrapperClasses = computed(() => ({
  disabled: isDisabled.value,
  'has-icon': showIcon.value,
  'input-wrapper--lg': props.size === 'lg',
  'input-wrapper--error': props.error,
}));
</script>

<template>
  <div
    class="input-wrapper"
    :class="wrapperClasses"
    role="group"
    :aria-disabled="isDisabled"
  >
    <span v-if="showIcon" class="input-icon" aria-hidden="true">
      <img v-if="iconIsUrl" :src="props.icon" alt="" />
      <i v-else :class="props.icon" aria-hidden="true"></i>
    </span>

    <input
      v-if="!showPlaceholder"
      v-model="value"
      :type="type"
      :disabled="isDisabled"
      class="input-field"
    />

    <input
      v-else
      :placeholder="placeholderText"
      v-model="value"
      :type="type"
      :disabled="isDisabled"
      class="input-field"
    />
  </div>
</template>
