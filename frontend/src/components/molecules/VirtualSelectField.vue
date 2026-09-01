<template>
  <q-select
    :model-value="modelValue"
    :options="onSearch ? serverOptions : filteredOptions"
    :loading="loading || serverLoading"
    :label="label"
    :placeholder="placeholder ?? undefined"
    :hint="hint ?? undefined"
    :error="error || loadError"
    :error-message="
      loadError ? $t('module_options_load_error') : (errorMessage ?? undefined)
    "
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
    <template v-if="onSearch" #no-option>
      <q-item dense>
        <q-item-section class="text-grey">
          {{ $t('common_type_to_search') }}
        </q-item-section>
      </q-item>
    </template>
  </q-select>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

interface SelectOption {
  label: string;
  value: string;
}

const props = defineProps<{
  modelValue: string | number | null | undefined;
  options?: SelectOption[];
  /**
   * Server-search mode (#2391 decision 4): options come from this
   * callback per keystroke instead of client-filtering `options` — for
   * option lists too large to ship (purchase: ~17k UNSPSC codes). The
   * caller owns the request (and any year guard); this component owns
   * the min-2 guard, debounce, loading/error state and staleness.
   */
  onSearch?: (query: string) => Promise<SelectOption[]>;
  /**
   * Server-search edit mode: the row's current {value, label} so
   * `map-options` can display the backend-resolved label with no fetch.
   */
  initialOption?: SelectOption | null;
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
  const opts = props.options ?? [];
  const q = searchQuery.value.toLowerCase();
  if (!q) return opts;
  return opts.filter(
    (o) =>
      o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
  );
});

const seeded = (): SelectOption[] =>
  props.initialOption ? [props.initialOption] : [];

const serverOptions = ref<SelectOption[]>(seeded());
const serverLoading = ref(false);
const loadError = ref(false);
// Stale-response guard: only the latest keystroke's outcome may touch the
// loading/error state — a slow failing request must never paint an error
// over a newer, successful option list (`update()` guards only options).
let requestSeq = 0;

async function filterFn(val: string, update: (cb: () => void) => void) {
  const search = props.onSearch;
  if (!search) {
    update(() => {
      searchQuery.value = val;
    });
    return;
  }
  const query = val.trim();
  // Mirrors the backend's min_length=2 — don't send requests it rejects.
  if (query.length < 2) {
    update(() => {
      serverOptions.value = seeded();
    });
    return;
  }
  const seq = ++requestSeq;
  serverLoading.value = true;
  loadError.value = false;
  try {
    const found = await search(query);
    if (seq !== requestSeq) return;
    update(() => {
      serverOptions.value = found;
    });
  } catch {
    // #2498-style: an empty list must be distinguishable from a failed
    // lookup — surface it on the field instead of a silent blank.
    if (seq !== requestSeq) return;
    update(() => {
      serverOptions.value = [];
    });
    loadError.value = true;
  } finally {
    if (seq === requestSeq) {
      serverLoading.value = false;
    }
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
