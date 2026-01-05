<template>
  <q-card
    flat
    class="module-total-result relative container"
    :class="{ 'module-total-result--validated': isValidated }"
  >
    <q-card-section class="module-total-result__container items-center">
      <div class="module-total-result__content">
        <template v-if="isValidated">
          <div class="text-body1 text-weight-medium q-mb-sm">
            {{
              $t('module_total_result_title', {
                type: type,
                typeI18n: $t(type),
              })
            }}
          </div>
          <h1 class="text-h1 text-weight-bold q-mb-none">
            {{
              $nOrDash(data, {
                options: {
                  ...moduleConfig?.numberFormatOptions,
                  maximumFractionDigits: 0,
                },
              })
            }}
          </h1>
          <p class="text-body2 text-secondary q-mb-none">
            {{ $t('module_total_result_title_unit', { type: type }) }}
          </p>
        </template>
        <!-- When NOT validated: Single line placeholder -->
        <template v-else>
          <div class="text-caption text-secondary">
            {{ $t('module_total_result_placeholder') }}
          </div>
        </template>
      </div>
      <!-- Right column: Validation button (vertically centered) -->
      <div class="module-total-result__button">
        <q-btn
          :outline="isValidated"
          :color="isValidated ? 'primary' : 'info'"
          :label="isValidated ? $t('common_unvalidate') : $t('common_validate')"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          @click="toggleValidation"
        />
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useTimelineStore } from 'src/stores/modules';
import { Module } from 'src/constant/modules';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULE_STATES } from 'src/constant/moduleStates';

const props = defineProps<{
  type: Module;
  data?: number;
  moduleConfig: ModuleConfig;
}>();

const timelineStore = useTimelineStore();

const isValidated = computed(() => {
  return timelineStore.itemStates[props.type] === MODULE_STATES.Validated;
});

function toggleValidation() {
  const newState = isValidated.value
    ? MODULE_STATES.InProgress
    : MODULE_STATES.Validated;
  timelineStore.setState(props.type, newState);
}
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-total-result {
  display: flex;
  flex-direction: column;
  justify-content: center;
  background-color: tokens.$module-result-bg;
  border: tokens.$module-result-border-weight solid
    tokens.$module-result-border-color;
  border-radius: tokens.$module-result-border-radius;
  padding: tokens.$module-result-padding-y tokens.$module-result-padding-x;
  transition: background-color 0.2s ease;
  min-height: 150px;

  &--validated {
    background-color: tokens.$module-result-bg-validated;
    border-color: tokens.$module-result-border-validated;
  }
}

.module-total-result__container {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: tokens.$spacing-xl;
  align-items: center;
}

.module-total-result__content {
  display: grid;
  grid-auto-flow: row;
  gap: 0.25rem;
}

.module-total-result__button {
  display: flex;
  align-items: center;
}
</style>
