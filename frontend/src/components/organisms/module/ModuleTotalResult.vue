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
        {{ sidebarMiniTooltip }}
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
        v-if="canValidate"
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
      <q-btn
        v-else-if="showContactHead && isValidated"
        icon="o_mail"
        color="info"
        unelevated
        no-caps
        size="xs"
        class="mtr-sidebar__mini-btn"
        type="a"
        :href="`mailto:${headOfUnitEmail}`"
      />
    </div>

    <div class="mtr-sidebar__body">
      <!-- header: status badge -->
      <div class="mtr-sidebar__header">
        <span class="mtr-sidebar__badge" :class="badgeClass">
          <q-icon
            v-if="statusDisplay.icon"
            :name="statusDisplay.icon"
            size="xs"
          />
          {{ $t(statusDisplay.label) }}
        </span>
      </div>

      <!-- value area — fixed height, stable layout -->
      <div
        v-if="canValidate || showContactHead"
        class="mtr-sidebar__value-area"
      >
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
        <template v-else-if="canValidate">
          <span class="mtr-sidebar__placeholder">
            {{ $t('module_total_result_placeholder') }}
          </span>
        </template>
        <template v-else>
          <div class="mtr-sidebar__value mtr-sidebar__value--empty">—</div>
        </template>
      </div>

      <!-- action button -->
      <q-btn
        v-if="canValidate"
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
      <q-btn
        v-else-if="showContactHead && isValidated"
        icon="o_mail"
        :label="$t('common_request_edit')"
        color="info"
        unelevated
        no-caps
        class="mtr-sidebar__btn text-weight-medium full-width"
        size="md"
        type="a"
        :href="`mailto:${headOfUnitEmail}`"
      >
        <q-tooltip anchor="center right" self="center left" :offset="[6, 0]">
          {{ $t('common_ask_head_of_unit') }}
        </q-tooltip>
      </q-btn>
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
        <template v-else-if="canValidate">
          <div class="text-caption text-secondary">
            {{ $t('module_total_result_placeholder') }}
          </div>
        </template>
        <template v-else>
          <h1 class="text-body1 text-weight-bold text-grey-5 q-mb-none">—</h1>
        </template>
      </div>
      <div v-if="canValidate" class="module-total-result__button">
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
      <div
        v-else-if="showContactHead && isValidated"
        class="module-total-result__button"
      >
        <q-btn
          icon="o_mail"
          :label="$t('common_request_edit')"
          color="info"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          type="a"
          :href="`mailto:${headOfUnitEmail}`"
        >
          <q-tooltip anchor="center right" self="center left" :offset="[6, 0]">
            {{ $t('common_ask_head_of_unit') }}
          </q-tooltip>
        </q-btn>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useTimelineStore } from 'src/stores/modules';
import { useAuthStore } from 'src/stores/auth';
import { useWorkspaceStore } from 'src/stores/workspace';
import { Module } from 'src/constant/modules';
import { ModuleConfig } from 'src/constant/moduleConfig';
import {
  MODULE_STATES,
  MODULE_STATUS_DISPLAY,
} from 'src/constant/moduleStates';
import { getModuleIconColors } from 'src/composables/useModuleIconColors';

const props = defineProps<{
  type: Module;
  data?: number;
  moduleConfig: ModuleConfig;
  sidebar?: boolean;
}>();

const { t } = useI18n();
const timelineStore = useTimelineStore();
const authStore = useAuthStore();
const workspaceStore = useWorkspaceStore();
const moduleColors = computed(() => getModuleIconColors(props.type));

// Validating a module's status is a unit-level action: hide the button from
// standard (own-scope) users, who never hold the `module.status` permission.
const canValidate = computed(() => authStore.hasUserCanValidateModuleStatus());

const moduleState = computed(() => timelineStore.itemStates[props.type]);

const isValidated = computed(
  () => moduleState.value === MODULE_STATES.Validated,
);

const headOfUnitEmail = computed(
  () => workspaceStore.selectedUnit?.principal_user_email ?? null,
);

// Non-validators (standard users) get a "request edit" affordance in place of
// the hidden validate button, but only once the module is validated — before
// that there is nothing to request an edit for.
const showContactHead = computed(
  () => !canValidate.value && !!headOfUnitEmail.value,
);

const toggleIcon = computed(() =>
  isValidated.value ? 'o_remove_circle' : 'o_check_circle',
);

// Three-state badge: validated / in progress / not started. Not started has no
// icon, so the template guards on `statusDisplay.icon` before rendering one.
const statusDisplay = computed(() => MODULE_STATUS_DISPLAY[moduleState.value]);

const badgeClass = computed(() => ({
  'mtr-sidebar__badge--validated':
    moduleState.value === MODULE_STATES.Validated,
  'mtr-sidebar__badge--progress':
    moduleState.value === MODULE_STATES.InProgress,
  'mtr-sidebar__badge--not-started':
    moduleState.value === MODULE_STATES.Default,
}));

const validationShortActionLabel = computed(() => {
  const action = isValidated.value
    ? t('common_unvalidate_short')
    : t('common_validate_short');
  return `${action} ${t(props.type)}`;
});

const sidebarMiniTooltip = computed(() =>
  canValidate.value
    ? validationShortActionLabel.value
    : t('common_ask_head_of_unit'),
);

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

    // Not started: neutral, no icon — distinct from the in-progress badge.
    &--not-started {
      background-color: rgba(0, 0, 0, 0.06);
      color: tokens.$mtr-color-muted;
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

    // Empty state (e.g. standard users before validation): a muted dash.
    &--empty {
      color: tokens.$mtr-color-muted;
    }
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
