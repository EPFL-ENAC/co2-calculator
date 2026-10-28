<template>
  <div class="destination-input-wrapper">
    <q-card
      bordered
      flat
      :class="{ 'destination-input-error': finalError }"
      class="destination-input-card"
    >
      <q-icon
        v-if="hint"
        :name="outlinedInfo"
        size="xs"
        color="grey-6"
        class="destination-input-hint-icon cursor-pointer"
      >
        <q-tooltip class="tooltip">{{ hint }}</q-tooltip>
      </q-icon>
      <q-card-section class="flex column q-pa-none position-relative">
        <div class="input-wrapper">
          <div class="destination-marker-outer">
            <div class="destination-marker-inner"></div>
          </div>
          <LocationSelectField
            v-if="transportMode && isAutocompleteEnabled"
            v-model="fromModel"
            :transport-mode="transportMode"
            class="marker-offset autocomplete-input"
            :label="$t(`${MODULES.ProfessionalTravel}-field-from`)"
            :placeholder="placeholders?.from"
            :disable="disable"
            @update:model-value="(val) => emit('update:from', val)"
            @location-selected="(loc) => emit('from-location-selected', loc)"
          />
          <q-input
            v-else
            class="marker-offset"
            dense
            borderless
            :model-value="from"
            :label="$t(`${MODULES.ProfessionalTravel}-field-from`)"
            :placeholder="placeholders?.from"
            hide-bottom-space
            :disable="disable || !transportMode"
            @update:model-value="
              (val) => emit('update:from', String(val ?? ''))
            "
          />
        </div>
        <q-separator class="marker-offset" color="grey-4" />
        <div class="input-wrapper">
          <div class="destination-marker-outer">
            <div class="destination-marker-inner"></div>
          </div>
          <LocationSelectField
            v-if="transportMode && isAutocompleteEnabled"
            v-model="toModel"
            :transport-mode="transportMode"
            class="marker-offset autocomplete-input"
            :label="$t(`${MODULES.ProfessionalTravel}-field-to`)"
            :placeholder="placeholders?.to"
            :disable="disable"
            @update:model-value="(val) => emit('update:to', val)"
            @location-selected="(loc) => emit('to-location-selected', loc)"
          />
          <q-input
            v-else
            class="marker-offset"
            dense
            borderless
            :model-value="to"
            :label="$t(`${MODULES.ProfessionalTravel}-field-to`)"
            :placeholder="placeholders?.to"
            hide-bottom-space
            :disable="disable || !transportMode"
            @update:model-value="(val) => emit('update:to', String(val ?? ''))"
          />
        </div>
        <q-btn
          round
          color="white"
          text-color="grey-4"
          size="md"
          class="swap-button"
          :disable="disable || !transportMode"
          @click="swapValues"
        >
          <q-icon :name="outlinedSwapHoriz" size="xs" />
        </q-btn>
      </q-card-section>
      <q-separator class="destination-separator" color="grey-4" />
    </q-card>
    <div v-if="finalError" class="destination-input-error-message">
      {{ finalErrorMessage }}
    </div>
    <div v-else class="destination-input-bottom-space"></div>
  </div>
</template>

<script setup lang="ts">
import {
  outlinedInfo,
  outlinedSwapHoriz,
} from '@quasar/extras/material-icons-outlined';
import { ref, computed, watch } from 'vue';
import { MODULES } from '@/constant/modules';
import { useI18n } from 'vue-i18n';
import LocationSelectField from '@/components/molecules/LocationSelectField.vue';

const { t: $t } = useI18n();

interface LocationSelection {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  iata_code?: string | null;
  country_code?: string | null;
  natural_key?: string;
}

const props = withDefaults(
  defineProps<{
    from?: string;
    to?: string;
    error?: boolean;
    errorMessage?: string;
    placeholders?: {
      from?: string;
      to?: string;
    };
    transportMode?: 'plane' | 'train';
    disable?: boolean;
    hint?: string;
  }>(),
  {
    from: '',
    to: '',
    error: false,
    errorMessage: '',
    transportMode: undefined,
    disable: false,
    hint: undefined,
    placeholders: () => ({
      from: '',
      to: '',
    }),
  },
);

const emit = defineEmits<{
  (e: 'update:from', value: string): void;
  (e: 'update:to', value: string): void;
  (e: 'from-location-selected', location: LocationSelection): void;
  (e: 'to-location-selected', location: LocationSelection): void;
  (e: 'swap'): void;
}>();

const fromModel = ref<string>('');
const toModel = ref<string>('');

const isAutocompleteEnabled = computed(() => !!props.transportMode);

const hasSameDestinationError = computed(() => {
  const fromValue = props.from?.trim() || '';
  const toValue = props.to?.trim() || '';
  return fromValue && toValue && fromValue === toValue;
});

const internalError = computed(() => hasSameDestinationError.value);
const internalErrorMessage = computed(() =>
  hasSameDestinationError.value
    ? $t(`${MODULES.ProfessionalTravel}-error-same-destination`)
    : '',
);

const finalError = computed(() => props.error || internalError.value);
const finalErrorMessage = computed(
  () => props.errorMessage || internalErrorMessage.value,
);

watch(
  () => props.from,
  (newVal) => {
    if (typeof newVal === 'string') {
      fromModel.value = newVal;
    }
  },
  { immediate: true },
);

watch(
  () => props.to,
  (newVal) => {
    if (typeof newVal === 'string') {
      toModel.value = newVal;
    }
  },
  { immediate: true },
);

watch(
  () => props.transportMode,
  (newMode, oldMode) => {
    if (oldMode !== undefined && newMode !== oldMode) {
      fromModel.value = '';
      toModel.value = '';
      emit('update:from', '');
      emit('update:to', '');
    }
  },
);

function swapValues() {
  const oldFrom = props.from;
  const oldTo = props.to;
  const oldFromModel = fromModel.value;
  const oldToModel = toModel.value;

  emit('update:from', oldTo);
  emit('update:to', oldFrom);
  emit('swap');

  if (isAutocompleteEnabled.value) {
    fromModel.value = oldToModel;
    toModel.value = oldFromModel;
  }
}
</script>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

:deep(.q-select__dropdown-icon),
:deep(.q-select-dropdown-icon),
:deep(.q-select_dropdown-icon) {
  display: none !important;
}

.destination-input-wrapper {
  margin-bottom: 4px;
}

.destination-input-card {
  position: relative;
  margin-bottom: 0;
  border: 1px solid tokens.$field-border-default;
}

.destination-input-hint-icon {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
}

.destination-input-card.destination-input-error {
  border-color: tokens.$color-status-error;
}

.input-wrapper {
  position: relative;
}

.marker-offset {
  margin-left: 32px;
}

.autocomplete-input {
  :deep(.q-field__control) {
    padding-left: 0;
  }
}

.swap-button {
  position: absolute;
  top: 50%;
  right: 16px;
  transform: translateY(-50%);
  border: 1px solid tokens.$field-border-default;
}

.destination-separator {
  position: absolute;
  top: 50%;
  left: 16px;
  transform: translate(-50%, -50%);
  background-color: tokens.$field-border-default;
  height: 40px;
  width: 1px;
  margin: 0;
}

.destination-marker-outer {
  position: absolute;
  top: 50%;
  left: calc(16px - tokens.$destination-marker-size-outer / 2);
  transform: translateY(-50%);
  width: tokens.$destination-marker-size-outer;
  height: tokens.$destination-marker-size-outer;
  background-color: tokens.$field-bg-default;
  border: 1px solid tokens.$field-border-default;
  border-radius: 999px;
  z-index: 1;
}

.destination-marker-inner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: tokens.$destination-marker-size-inner;
  height: tokens.$destination-marker-size-inner;
  background-color: tokens.$field-bg-default;
  border: 1px solid tokens.$field-border-default;
  border-radius: 999px;
  z-index: 1;
}

.destination-input-error-message {
  color: tokens.$color-status-error;
  font-size: 12px;
  line-height: 1.5;
  padding-top: 4px;
  padding-left: 12px;
  min-height: 20px;
}

.destination-input-bottom-space {
  min-height: 20px;
}
</style>
