<template>
  <q-select
    :model-value="modelValue"
    :options="options"
    :loading="loading"
    :label="label"
    :placeholder="placeholder ?? undefined"
    :hint="hint ?? undefined"
    :error="error || loadError"
    :error-message="
      loadError ? $t('module_options_load_error') : (errorMessage ?? undefined)
    "
    :readonly="readonly"
    :disable="disable"
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
    <template #no-option>
      <q-item dense>
        <q-item-section class="text-grey">
          {{ $t('common_type_to_search') }}
        </q-item-section>
      </q-item>
    </template>
  </q-select>
</template>

<script setup lang="ts">
// Server-side typeahead select (#2391 decision 4): options come from the
// `taxonomies/.../options` search endpoint per keystroke — built for kind
// fields whose option list is too large to ship as a taxonomy tree
// (purchase: ~17k UNSPSC codes). Same visual contract as
// VirtualSelectField; the option list is what differs.
import { ref } from 'vue';
import { searchDataEntryOptions } from '@/api/taxonomies';

interface SelectOption {
  label: string;
  value: string;
}

const props = defineProps<{
  modelValue: string | number | null | undefined;
  moduleType: string;
  submoduleType: string;
  /** Year whose factors to search; null = not resolvable yet, no fetch. */
  year: number | string | null;
  /**
   * Edit mode: the row's current {value, label} so `map-options` can
   * display the backend-resolved label without any option fetch.
   */
  initialOption?: SelectOption | null;
  label?: string;
  placeholder?: string | null;
  hint?: string | null;
  error?: boolean;
  errorMessage?: string | null;
  readonly?: boolean;
  disable?: boolean;
  icon?: string;
}>();

defineEmits<{
  (e: 'update:modelValue', value: string | number | null): void;
}>();

const options = ref<SelectOption[]>(
  props.initialOption ? [props.initialOption] : [],
);
const loading = ref(false);
const loadError = ref(false);

const seeded = (): SelectOption[] =>
  props.initialOption ? [props.initialOption] : [];

async function filterFn(val: string, update: (cb: () => void) => void) {
  const query = val.trim();
  // Mirrors the backend's min_length=2 — don't send requests it rejects.
  if (query.length < 2 || props.year === null) {
    update(() => {
      options.value = seeded();
    });
    return;
  }
  loading.value = true;
  loadError.value = false;
  try {
    const found = await searchDataEntryOptions(
      props.moduleType,
      props.submoduleType,
      query,
      props.year,
    );
    update(() => {
      options.value = found.map((o) => ({ value: o.name, label: o.label }));
    });
  } catch {
    // #2498-style: an empty list must be distinguishable from a failed
    // lookup — surface it on the field instead of a silent blank.
    update(() => {
      options.value = [];
    });
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="scss">
:deep(.q-field__native) {
  flex-wrap: nowrap;
}
</style>
