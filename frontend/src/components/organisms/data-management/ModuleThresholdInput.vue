<script setup lang="ts">
import { computed } from 'vue';
import type { ModuleThreshold, ThresholdType } from 'src/constant/modules';

const props = defineProps<{
  modelValue: ModuleThreshold;
  type: ThresholdType;
}>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: ModuleThreshold): void;
}>();

const selected = computed({
  get: () => props.modelValue,
  set: (val: ModuleThreshold) => {
    emit('update:modelValue', val);
  },
});

const isModuleType = computed(
  () => selected.value.threshold.type === props.type,
);

function onSelect() {
  if (isModuleType.value) {
    return;
  }
  selected.value.threshold.type = props.type;
  onTypeChange();
}

function onTypeChange() {
  if (props.type === 'median') {
    selected.value.threshold.value = undefined;
    return;
  }
  selected.value.threshold.value = 0;
}
function onValueChange() {
  if (
    selected.value.threshold.type !== 'median' &&
    typeof selected.value.threshold.value !== 'number'
  ) {
    // ensure not undefined value or empty string
    selected.value.threshold.value = 0;
  }
}
</script>

<template>
  <q-card
    flat
    bordered
    class="q-px-lg card"
    :class="isModuleType ? 'active' : ''"
    @click="onSelect"
  >
    <q-banner
      inline-actions
      class="q-pa-none"
      style="background-color: transparent"
    >
      <span class="text-h5 text-weight-medium">
        {{ $t(`threshold_${type}_title`) }}
      </span>

      <template #action>
        <q-radio
          v-model="selected.threshold.type"
          :val="type"
          :color="isModuleType ? 'accent' : 'grey-5'"
          @update:model-value="onTypeChange"
        />
      </template>
    </q-banner>
    <div class="text-body2 text-secondary">
      {{ $t(`threshold_${type}_description`) }}
    </div>
    <q-card-actions
      v-if="selected.threshold.type === type"
      class="q-my-lg q-pa-none card-footer"
    >
      <q-input
        v-if="type !== 'median'"
        v-model.number="selected.threshold.value"
        :disable="!isModuleType"
        type="number"
        min="0"
        :label="$t(`threshold_${type}_value`)"
        dense
        outlined
        class="bg-white"
        @update:model-value="onValueChange"
      />
      <div v-else class="text-body2">
        <q-icon name="circle" size="xs" class="q-mr-sm" color="positive" />
        {{ $t('threshold_median_info') }}
      </div>
    </q-card-actions>
  </q-card>
</template>

<style lang="scss" scoped>
.card {
  min-height: 180px;
  position: relative;
}
.card-footer {
  position: absolute;
  bottom: 0;
}
.active {
  background-color: rgba($accent, 0.04);
  border-color: $accent;
}
</style>
