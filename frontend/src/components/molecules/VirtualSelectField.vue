<template>
  <q-select
    :model-value="modelValue"
    :options="filteredOptions"
    :loading="loading"
    :label="label"
    :placeholder="placeholder ?? undefined"
    :hint="hint ?? undefined"
    :error="error"
    :error-message="errorMessage ?? undefined"
    :readonly="readonly"
    :disable="disable"
    :hide-bottom-space="hideBottomSpace"
    :title="title"
    use-input
    fill-input
    hide-selected
    input-debounce="300"
    dense
    outlined
    emit-value
    map-options
    @filter="filterFn"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template v-if="icon" #prepend>
      <q-icon :name="icon" color="grey-6" size="xs" />
    </template>
  </q-select>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

const props = defineProps<{
  modelValue: string | number | null | undefined;
  options: Array<{ label: string; value: string }>;
  loading?: boolean;
  label?: string;
  placeholder?: string | null;
  hint?: string | null;
  error?: boolean;
  errorMessage?: string | null;
  readonly?: boolean;
  disable?: boolean;
  icon?: string;
  hideBottomSpace?: boolean;
  title?: string;
}>();

defineEmits<{
  (e: 'update:modelValue', value: string | number | null): void;
}>();

const searchQuery = ref('');

const filteredOptions = computed(() => {
  const q = searchQuery.value.toLowerCase();
  if (!q) return props.options;
  return props.options.filter(
    (o) =>
      o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
  );
});

function filterFn(val: string, update: (cb: () => void) => void) {
  update(() => {
    searchQuery.value = val;
  });
}
</script>

<style scoped lang="scss">
:deep(.q-field__native) {
  flex-wrap: nowrap;
}

:deep(.q-chip) {
  min-width: 0;
  flex-shrink: 1;
}

:deep(.q-chip__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
