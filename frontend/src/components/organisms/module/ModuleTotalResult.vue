<template>
  <!-- ─── Sidebar variant ─────────────────────────────────────────── -->
  <div v-if="sidebar" class="mtr-sidebar">
    <!-- collapsed mini view -->
    <div class="mtr-sidebar__mini">
      <q-tooltip
        anchor="center right"
        self="center left"
        :offset="[6, 0]"
        class="sidebar-tooltip"
      >
        {{ validationShortActionLabel }}
      </q-tooltip>
      <template v-if="isValidated">
        <span
          class="mtr-sidebar__mini-value"
          :style="{ color: moduleColors.buttonTextColor }"
        >
          {{ moduleConfig.totalFormatter(data) }}
        </span>
        <span class="mtr-sidebar__mini-unit">
          {{ $t('module_total_result_title_unit', { type }) }}
        </span>
      </template>
      <q-btn
        :icon="toggleIcon"
        unelevated
        no-caps
        size="xs"
        class="mtr-sidebar__mini-btn"
        :style="{
          background: moduleColors.bgColorLighter,
          color: moduleColors.buttonTextColor,
          border: `1px solid ${moduleColors.buttonTextColor}`,
        }"
        @click="toggleValidation"
      />
    </div>

    <div class="mtr-sidebar__body">
      <!-- header: status badge -->
      <div class="mtr-sidebar__header">
        <span
          class="mtr-sidebar__badge"
          :class="{
            'mtr-sidebar__badge--validated': isValidated,
            'mtr-sidebar__badge--progress': !isValidated,
          }"
        >
          <q-icon :name="statusIcon" size="xs" />
          {{ statusLabel }}
        </span>
      </div>

      <!-- value area — fixed height, stable layout -->
      <div class="mtr-sidebar__value-area">
        <template v-if="isValidated">
          <div
            class="mtr-sidebar__value"
            :style="{ color: moduleColors.buttonTextColor }"
          >
            {{ moduleConfig.totalFormatter(data) }}
          </div>
          <span class="mtr-sidebar__unit">
            {{ $t('module_total_result_title_unit', { type }) }}
          </span>
        </template>
        <template v-else>
          <span class="mtr-sidebar__placeholder">
            {{ $t('module_total_result_placeholder') }}
          </span>
        </template>
      </div>

      <!-- action button -->
      <q-btn
        :icon="toggleIcon"
        :label="validationShortActionLabel"
        unelevated
        no-caps
        class="mtr-sidebar__btn text-weight-medium full-width"
        size="md"
        :style="{
          background: moduleColors.bgColorLighter,
          color: moduleColors.buttonTextColor,
          border: `1px solid ${moduleColors.buttonTextColor}`,
        }"
        @click="toggleValidation"
      />
    </div>
  </div>

  <!-- ─── Default (module page) variant ───────────────────────────── -->
  <q-card
    v-else
    flat
    class="module-total-result relative container"
    :class="{ 'module-total-result--validated': isValidated }"
    :style="accentBarStyle"
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
          <h1
            class="text-h1 text-weight-bold q-mb-none"
            :style="{ color: moduleColors.buttonTextColor }"
          >
            {{ moduleConfig.totalFormatter(data) }}
          </h1>
          <p class="text-body2 text-secondary q-mb-none">
            {{ $t('module_total_result_title_unit', { type: type }) }}
          </p>
        </template>
        <template v-else>
          <div class="text-caption text-secondary">
            {{ $t('module_total_result_placeholder') }}
          </div>
        </template>
      </div>
      <div class="module-total-result__button">
        <q-btn
          :outline="isValidated"
          :label="validationLabel"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          :style="validationBtnStyle"
          @click="toggleValidation"
        />
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useTimelineStore } from 'src/stores/modules';
import { Module } from 'src/constant/modules';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { getModuleIconColors } from 'src/composables/useModuleIconColors';

const props = defineProps<{
  type: Module;
  data?: number;
  moduleConfig: ModuleConfig;
  sidebar?: boolean;
}>();

const { t } = useI18n();
const timelineStore = useTimelineStore();
const moduleColors = computed(() => getModuleIconColors(props.type));

const isValidated = computed(
  () => timelineStore.itemStates[props.type] === MODULE_STATES.Validated,
);

const toggleIcon = computed(() =>
  isValidated.value ? 'o_remove_circle' : 'o_check_circle',
);

const statusIcon = computed(() =>
  isValidated.value ? 'o_check_circle' : 'o_pending',
);

const statusLabel = computed(() =>
  isValidated.value
    ? t('module_status_validated')
    : t('module_status_in_progress'),
);

const validationShortActionLabel = computed(() => {
  const action = isValidated.value
    ? t('common_unvalidate_short')
    : t('common_validate_short');
  return `${action} ${t(props.type)}`;
});

const validationLabel = computed(() =>
  isValidated.value ? t('common_unvalidate') : t('common_validate'),
);

const accentBarStyle = computed(() =>
  isValidated.value ? { '--accent-bar-bg': moduleColors.value.bgColor } : {},
);

const validationBtnStyle = computed(() =>
  isValidated.value
    ? {
        borderColor: moduleColors.value.buttonTextColor,
        color: moduleColors.value.buttonTextColor,
      }
    : {
        background: moduleColors.value.bgColorLighter,
        color: moduleColors.value.buttonTextColor,
        border: `1px solid ${moduleColors.value.buttonTextColor}`,
      },
);

function toggleValidation() {
  const newState = isValidated.value
    ? MODULE_STATES.InProgress
    : MODULE_STATES.Validated;
  timelineStore.setState(props.type, newState);
}
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

/* ── Sidebar variant ───────────────────────────────────────────────── */
.mtr-sidebar {
  flex-shrink: 0;
  border-bottom: tokens.$mtr-sidebar-border-bottom-width solid
    tokens.$sidebar-border-color;

  &__mini {
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: tokens.$mtr-sidebar-mini-padding;
    gap: tokens.$mtr-sidebar-mini-gap;
  }

  &__mini-value {
    font-size: tokens.$mtr-sidebar-mini-value-font-size;
    font-weight: tokens.$mtr-sidebar-mini-value-font-weight;
    line-height: tokens.$text-line-height-none;
    letter-spacing: tokens.$mtr-sidebar-mini-value-letter-spacing;
  }

  &__mini-unit {
    font-size: tokens.$mtr-sidebar-mini-unit-font-size;
    color: tokens.$mtr-color-muted;
    line-height: tokens.$mtr-sidebar-mini-unit-line-height;
    text-align: center;
  }

  &__mini-btn {
    margin-top: tokens.$mtr-sidebar-mini-btn-margin-top;
    border-radius: tokens.$mtr-sidebar-mini-btn-border-radius;
    width: tokens.$mtr-sidebar-mini-btn-size !important;
    height: tokens.$mtr-sidebar-mini-btn-size !important;
    min-height: unset !important;
    padding: 0 !important;
  }

  &__mini-tooltip {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: tokens.$mtr-sidebar-mini-tooltip-gap;
    padding: tokens.$mtr-sidebar-mini-tooltip-padding-y 0;
  }

  &__mini-tooltip-value {
    font-size: tokens.$mtr-sidebar-mini-tooltip-value-font-size;
    font-weight: tokens.$mtr-sidebar-mini-tooltip-value-font-weight;
    line-height: tokens.$text-line-height-none;
    letter-spacing: tokens.$mtr-sidebar-mini-tooltip-value-letter-spacing;
  }

  &__mini-tooltip-unit {
    font-size: tokens.$mtr-sidebar-mini-tooltip-unit-font-size;
    color: tokens.$mtr-tooltip-text-muted;
  }

  &__mini-tooltip-placeholder {
    font-size: tokens.$mtr-sidebar-mini-tooltip-placeholder-font-size;
    color: tokens.$mtr-tooltip-text-muted;
    max-width: tokens.$mtr-sidebar-mini-tooltip-placeholder-max-width;
  }

  &__body {
    padding: tokens.$mtr-sidebar-body-padding;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: tokens.$mtr-sidebar-body-gap;
  }

  &__header {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-start;
  }

  &__badge {
    display: inline-flex;
    align-items: center;
    gap: tokens.$mtr-sidebar-badge-gap;
    font-size: tokens.$mtr-sidebar-badge-font-size;
    font-weight: tokens.$mtr-sidebar-badge-font-weight;
    padding: tokens.$mtr-sidebar-badge-padding;
    border-radius: tokens.$mtr-sidebar-badge-radius;

    &--validated {
      background-color: rgba(
        var(--q-positive-rgb, 33, 186, 69),
        tokens.$mtr-sidebar-badge-bg-opacity-validated
      );
      color: var(--q-positive);
    }

    &--progress {
      background-color: rgba(
        var(--q-warning-rgb, 242, 192, 56),
        tokens.$mtr-sidebar-badge-bg-opacity-progress
      );
      color: var(--q-warning);
    }
  }

  // Fixed-height area so layout doesn't jump between states
  &__value-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: tokens.$mtr-sidebar-value-area-min-height;
    width: 100%;
  }

  &__placeholder {
    font-size: tokens.$mtr-sidebar-placeholder-font-size;
    color: tokens.$mtr-color-muted;
    margin-top: tokens.$mtr-sidebar-placeholder-margin-top;
    line-height: tokens.$mtr-sidebar-placeholder-line-height;
    max-width: tokens.$mtr-sidebar-placeholder-max-width;
  }

  &__value {
    font-size: tokens.$mtr-sidebar-value-font-size;
    font-weight: tokens.$mtr-sidebar-value-font-weight;
    line-height: tokens.$text-line-height-none;
    letter-spacing: tokens.$mtr-sidebar-value-letter-spacing;
  }

  &__unit {
    display: block;
    font-size: tokens.$mtr-sidebar-unit-font-size;
    font-weight: tokens.$text-weight-regular;
    color: tokens.$mtr-color-muted-dark;
    letter-spacing: 0;
    margin-top: tokens.$mtr-sidebar-unit-margin-top;
  }

  &__btn {
    border-radius: tokens.$mtr-sidebar-btn-border-radius;
  }
}

/* ── Default (module page) variant ────────────────────────────────── */
.module-total-result {
  display: flex;
  flex-direction: column;
  justify-content: center;
  background-color: tokens.$module-result-bg;
  border: tokens.$module-result-border-weight solid
    tokens.$module-result-border-color;
  border-radius: tokens.$module-result-border-radius;
  padding: tokens.$module-result-padding-y tokens.$module-result-padding-x;
  transition: background-color tokens.$transition-default;
  min-height: tokens.$mtr-card-min-height;

  &--validated {
    background-color: tokens.$module-result-bg-validated;
    border-color: tokens.$module-result-border-validated;
    overflow: hidden;

    &::before {
      content: '';
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: tokens.$mtr-card-accent-width;
      background: var(--accent-bar-bg);
      border-radius: tokens.$module-result-border-radius 0 0
        tokens.$module-result-border-radius;
    }
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
  gap: tokens.$mtr-content-gap;
}

.module-total-result__button {
  display: flex;
  align-items: center;
}
</style>
