<template>
  <div class="destination-input-wrapper">
    <q-card
      bordered
      flat
      :class="{ 'destination-input-error': finalError }"
      class="destination-input-card"
    >
      <q-card-section class="flex column q-pa-none position-relative">
        <div class="input-wrapper">
          <div class="destination-marker-outer">
            <div class="destination-marker-inner"></div>
          </div>
          <q-select
            v-if="transportMode && isAutocompleteEnabled"
            v-model="fromModel"
            :options="fromOptions"
            :loading="loadingFrom"
            use-input
            input-debounce="100"
            hide-selected
            fill-input
            option-label="name"
            dense
            borderless
            hide-dropdown-icon
            class="marker-offset autocomplete-input"
            :label="$t(`${MODULES.ProfessionalTravel}-field-from`)"
            :placeholder="placeholders?.from"
            hide-bottom-space
            :disable="fieldDisabled || !transportMode"
            @filter="(val, update) => filterFrom(val, update)"
            @update:model-value="handleFromSelection"
          >
            <template #no-option>
              <q-item>
                <q-item-section class="text-grey">
                  {{
                    loadingFrom
                      ? $t('common_searching') || 'Searching...'
                      : $t('common_no_results') || 'No results'
                  }}
                </q-item-section>
              </q-item>
            </template>
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
          </q-select>
          <q-input
            v-else
            class="marker-offset"
            dense
            borderless
            :model-value="from"
            :label="$t(`${MODULES.ProfessionalTravel}-field-from`)"
            :placeholder="placeholders?.from"
            hide-bottom-space
            :disable="fieldDisabled || !transportMode"
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
          <q-select
            v-if="transportMode && isAutocompleteEnabled"
            v-model="toModel"
            :options="toOptions"
            :loading="loadingTo"
            use-input
            input-debounce="100"
            hide-selected
            fill-input
            option-label="name"
            dense
            borderless
            hide-dropdown-icon
            class="marker-offset autocomplete-input"
            :label="$t(`${MODULES.ProfessionalTravel}-field-to`)"
            :placeholder="placeholders?.to"
            hide-bottom-space
            :disable="fieldDisabled || !transportMode"
            @filter="(val, update) => filterTo(val, update)"
            @update:model-value="handleToSelection"
          >
            <template #no-option>
              <q-item>
                <q-item-section class="text-grey">
                  {{
                    loadingTo
                      ? $t('common_searching') || 'Searching...'
                      : $t('common_no_results') || 'No results'
                  }}
                </q-item-section>
              </q-item>
            </template>
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
          </q-select>
          <q-input
            v-else
            class="marker-offset"
            dense
            borderless
            :model-value="to"
            :label="$t(`${MODULES.ProfessionalTravel}-field-to`)"
            :placeholder="placeholders?.to"
            hide-bottom-space
            :disable="fieldDisabled || !transportMode"
            @update:model-value="(val) => emit('update:to', String(val ?? ''))"
          />
        </div>
        <q-btn
          round
          color="white"
          text-color="grey-4"
          size="md"
          class="swap-button"
          :disable="fieldDisabled || !transportMode"
          @click="swapValues"
        >
          <q-icon name="o_swap_horiz" size="xs" />
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
import { ref, computed, watch, watchEffect } from 'vue';
import { MODULES } from 'src/constant/modules';
import { useI18n } from 'vue-i18n';
import { searchLocations, calculateDistance } from 'src/api/locations';
import type { Location } from 'src/constant/locations';
import type { ModuleField } from 'src/constant/moduleConfig';
import type { AllSubmoduleTypes, Module } from 'src/constant/modules';

const { t: $t } = useI18n();

interface LocationSelection {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
}

const props = withDefaults(
  defineProps<{
    modelValue: string | null;
    moduleType: Module | string;
    submoduleType: AllSubmoduleTypes;
    field: ModuleField;
    entry: Record<string, unknown>;
    from?: string;
    to?: string;
    error?: boolean;
    errorMessage?: string;
    placeholders?: {
      from?: string;
      to?: string;
    };
    transportMode?: 'plane' | 'train';
    originLocationId?: number;
    destinationLocationId?: number;
    numberOfTrips?: number;
  }>(),
  {
    from: '',
    to: '',
    error: false,
    errorMessage: '',
    transportMode: undefined,
    disable: false,
    placeholders: () => ({
      from: '',
      to: '',
    }),
    originLocationId: undefined,
    destinationLocationId: undefined,
    numberOfTrips: 1,
  },
);

const emit = defineEmits<{
  (e: 'update:from', value: string): void;
  (e: 'update:to', value: string): void;
  (e: 'from-location-selected', location: LocationSelection): void;
  (e: 'to-location-selected', location: LocationSelection): void;
  (e: 'swap'): void;
  (e: 'update:originLocationId', value: number | undefined): void;
  (e: 'update:destinationLocationId', value: number | undefined): void;
  (e: 'distance-calculated', value: number | null): void;
}>();

const fromOptions = ref<Location[]>([]);
const toOptions = ref<Location[]>([]);
const loadingFrom = ref(false);
const loadingTo = ref(false);
const fromModel = ref<string>('');
const toModel = ref<string>('');
const internalOriginLocationId = ref<number | undefined>(
  props.originLocationId,
);
const internalDestinationLocationId = ref<number | undefined>(
  props.destinationLocationId,
);

const fieldDisabled = ref<boolean>(false);

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

watchEffect(() => {
  if (typeof props.field.disable === 'function') {
    fieldDisabled.value = props.field.disable(props.submoduleType, props.entry);
  } else {
    fieldDisabled.value = !!props.field.disable;
  }
});

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

watch(fromModel, (newVal) => {
  if (newVal && typeof newVal === 'object') {
    fromModel.value = (newVal as Location).name || '';
  }
});

watch(toModel, (newVal) => {
  if (newVal && typeof newVal === 'object') {
    toModel.value = (newVal as Location).name || '';
  }
});

watch(
  () => props.transportMode,
  (newMode, oldMode) => {
    if (oldMode !== undefined && newMode !== oldMode) {
      // Clear options
      fromOptions.value = [];
      toOptions.value = [];
      loadingFrom.value = false;
      loadingTo.value = false;
      fromModel.value = '';
      toModel.value = '';
      emit('update:from', '');
      emit('update:to', '');
      internalOriginLocationId.value = undefined;
      internalDestinationLocationId.value = undefined;
      emit('update:originLocationId', undefined);
      emit('update:destinationLocationId', undefined);
      emit('distance-calculated', null);
    }
  },
);

watch(
  () => props.originLocationId,
  (newVal) => {
    internalOriginLocationId.value = newVal;
  },
);

watch(
  () => props.destinationLocationId,
  (newVal) => {
    internalDestinationLocationId.value = newVal;
  },
);

watch(
  () => props.numberOfTrips,
  () => {
    void calculateAndEmitDistance();
  },
);

async function calculateAndEmitDistance() {
  if (!props.transportMode) return;
  if (
    internalOriginLocationId.value === undefined ||
    internalDestinationLocationId.value === undefined
  ) {
    emit('distance-calculated', null);
    return;
  }
  const distance = await calculateDistance(
    internalOriginLocationId.value,
    internalDestinationLocationId.value,
    props.transportMode,
    props.numberOfTrips || 1,
  );
  emit('distance-calculated', distance);
}

async function filterFrom(val: string, update: (fn: () => void) => void) {
  if (!props.transportMode || val.length < 2) {
    update(() => {
      fromOptions.value = [];
    });
    return;
  }

  loadingFrom.value = true;
  try {
    const results = await searchLocations(val, props.transportMode, 10);
    update(() => {
      fromOptions.value = results;
    });
  } catch (error) {
    console.error('Error fetching from locations:', error);
    update(() => {
      fromOptions.value = [];
    });
  } finally {
    loadingFrom.value = false;
  }
}

async function filterTo(val: string, update: (fn: () => void) => void) {
  if (!props.transportMode || val.length < 2) {
    update(() => {
      toOptions.value = [];
    });
    return;
  }

  loadingTo.value = true;
  try {
    const results = await searchLocations(val, props.transportMode, 10);
    update(() => {
      toOptions.value = results;
    });
  } catch (error) {
    console.error('Error fetching to locations:', error);
    update(() => {
      toOptions.value = [];
    });
  } finally {
    loadingTo.value = false;
  }
}

function handleFromSelection(value: Location | string | null) {
  if (!value) {
    emit('update:from', '');
    fromModel.value = '';
    internalOriginLocationId.value = undefined;
    emit('update:originLocationId', undefined);
    emit('distance-calculated', null);
    return;
  }

  if (typeof value === 'string') {
    fromModel.value = value;
    emit('update:from', value);
    return;
  }

  fromModel.value = value.name;
  emit('update:from', value.name);
  emit('from-location-selected', {
    id: value.id,
    name: value.name,
    latitude: value.latitude,
    longitude: value.longitude,
  });
  internalOriginLocationId.value = value.id;
  emit('update:originLocationId', value.id);
  void calculateAndEmitDistance();
}

function handleToSelection(value: Location | string | null) {
  if (!value) {
    emit('update:to', '');
    toModel.value = '';
    internalDestinationLocationId.value = undefined;
    emit('update:destinationLocationId', undefined);
    emit('distance-calculated', null);
    return;
  }

  if (typeof value === 'string') {
    toModel.value = value;
    emit('update:to', value);
    return;
  }

  toModel.value = value.name;
  emit('update:to', value.name);
  emit('to-location-selected', {
    id: value.id,
    name: value.name,
    latitude: value.latitude,
    longitude: value.longitude,
  });
  internalDestinationLocationId.value = value.id;
  emit('update:destinationLocationId', value.id);
  void calculateAndEmitDistance();
}

function swapValues() {
  const oldFrom = props.from;
  const oldTo = props.to;
  const oldFromModel = fromModel.value;
  const oldToModel = toModel.value;

  const oldOriginId = internalOriginLocationId.value;
  const oldDestinationId = internalDestinationLocationId.value;
  internalOriginLocationId.value = oldDestinationId;
  internalDestinationLocationId.value = oldOriginId;
  emit('update:originLocationId', oldDestinationId);
  emit('update:destinationLocationId', oldOriginId);

  emit('update:from', oldTo);
  emit('update:to', oldFrom);
  emit('swap');

  if (isAutocompleteEnabled.value) {
    fromModel.value = oldToModel;
    toModel.value = oldFromModel;
  }

  void calculateAndEmitDistance();
}
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

:deep(.q-select__dropdown-icon),
:deep(.q-select-dropdown-icon),
:deep(.q-select_dropdown-icon) {
  display: none !important;
}

.destination-input-wrapper {
  margin-bottom: 4px;
}

.destination-input-card {
  margin-bottom: 0;
  border: 1px solid tokens.$field-border-default;
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
