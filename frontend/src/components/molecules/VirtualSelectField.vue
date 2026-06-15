<template>
  <q-select
    :model-value="modelValue"
    :options="visibleOptions"
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
    @virtual-scroll="onVirtualScroll"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template v-if="icon" #prepend>
      <q-icon :name="icon" color="grey-6" size="xs" />
    </template>
  </q-select>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

const PAGE_SIZE = 50;

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
const pageCount = ref(1);

const filteredOptions = computed(() => {
  const q = searchQuery.value.toLowerCase();
  if (!q) return props.options;
  return props.options.filter(
    (o) =>
      o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
  );
});

const visibleOptions = computed(() => {
  const base = filteredOptions.value.slice(0, pageCount.value * PAGE_SIZE);
  const sel = props.modelValue != null ? String(props.modelValue) : null;
  if (sel && !base.some((o) => o.value === sel)) {
    const found = filteredOptions.value.find((o) => o.value === sel);
    if (found) return [found, ...base];
  }
  return base;
});

function filterFn(val: string, update: (cb: () => void) => void) {
  update(() => {
    searchQuery.value = val;
    pageCount.value = 1;
  });
}

function onVirtualScroll({ to }: { to: number }) {
  const showing = pageCount.value * PAGE_SIZE;
  if (to >= showing - 5 && showing < filteredOptions.value.length) {
    pageCount.value++;
  }
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
