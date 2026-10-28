<template>
  <q-select
    :model-value="modelValue"
    :options="options"
    :loading="loading"
    use-input
    input-debounce="300"
    hide-selected
    fill-input
    option-label="name"
    dense
    borderless
    hide-dropdown-icon
    :label="label"
    :placeholder="placeholder"
    hide-bottom-space
    :disable="disable"
    @filter="(val, update) => filter(val, update)"
    @virtual-scroll="onVirtualScroll"
    @update:model-value="handleSelection"
  >
    <template #option="scope">
      <q-item v-bind="scope.itemProps">
        <q-item-section>
          <q-item-label>{{ scope.opt.name }}</q-item-label>
          <q-item-label
            v-if="scope.opt.iata_code || scope.opt.country_code"
            caption
            class="text-grey"
          >
            {{
              [scope.opt.iata_code, scope.opt.country_code]
                .filter(Boolean)
                .join(', ')
            }}
          </q-item-label>
        </q-item-section>
      </q-item>
    </template>
    <template #no-option>
      <q-item dense>
        <q-item-section :class="loadError ? 'text-negative' : 'text-grey'">
          {{ $t(emptyLabel) }}
        </q-item-section>
      </q-item>
    </template>
    <template v-if="loadError" #after-options>
      <q-item dense>
        <q-item-section class="text-negative">
          {{ $t('module_options_load_error') }}
        </q-item-section>
      </q-item>
    </template>
  </q-select>
</template>

<script setup lang="ts">
import { watch } from 'vue';
import { useLocationSearch } from '@/composables/useLocationSearch';
import type { Location, TransportMode } from '@/constant/locations';

/** One server-searched station or airport field, with infinite scroll (#939). */
const props = withDefaults(
  defineProps<{
    modelValue: string;
    transportMode: TransportMode;
    label: string;
    placeholder?: string;
    disable?: boolean;
  }>(),
  {
    placeholder: undefined,
    disable: false,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'location-selected', location: Location): void;
}>();

const {
  options,
  loading,
  loadError,
  emptyLabel,
  filter,
  onVirtualScroll,
  reset,
} = useLocationSearch(() => props.transportMode);

// Results belong to one mode: a switch drops the list and any request in
// flight, before the next search refills it.
watch(() => props.transportMode, reset);

function handleSelection(value: Location | string | null) {
  if (!value) {
    emit('update:modelValue', '');
    return;
  }

  if (typeof value === 'string') {
    emit('update:modelValue', value);
    return;
  }

  emit('update:modelValue', value.name);
  emit('location-selected', { ...value });
}
</script>
