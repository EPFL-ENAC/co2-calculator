<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES } from 'src/constant/modules';
import { MODULES_CONFIG } from 'src/constant/module-config';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import { getModuleTypeId, MODULE_STATES } from 'src/constant/moduleStates';
import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useAuthStore } from 'src/stores/auth';
import { PermissionAction } from 'src/stores/auth';
import type { Module } from 'src/constant/modules';
import { useTimelineStore } from 'src/stores/modules';
import { useModuleStore } from 'src/stores/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { formatTonnesCO2 } from 'src/utils/number';

const { t } = useI18n();
const workspaceStore = useWorkspaceStore();
const authStore = useAuthStore();
const moduleStore = useModuleStore();
const yearConfigStore = useYearConfigStore();

const currentYear = computed(
  () => workspaceStore.selectedYear ?? new Date().getFullYear(),
);

const validatedTotals = computed(() => {
  const carbonReportId = timelineStore.currentCarbonReportId;
  if (
    carbonReportId &&
    carbonReportId !== moduleStore.validatedTotalsCarbonReportId
  ) {
    moduleStore.getValidatedTotals(carbonReportId);
  }
  return moduleStore.state.validatedTotals;
});

const firstEditableModule = computed(() => {
  return Object.values(MODULES).find((module) =>
    hasModulePermission(module, PermissionAction.EDIT),
  );
});

const moduleCardTotals = computed(() => {
  const modules = validatedTotals.value?.modules;
  return Object.fromEntries(
    MODULE_CARDS.map(({ module }) => [
      module,
      modules?.[getModuleTypeId(module)] ?? null,
    ]),
  );
});

function hasModulePermission(
  module: Module,
  action: PermissionAction,
): boolean {
  return authStore.hasUserModulePermission(module, action);
}
const timelineStore = useTimelineStore();

const moduleCardsWithStatus = computed(() =>
  MODULE_CARDS.filter(
    (card) =>
      yearConfigStore.isModuleVisible(card.module) &&
      authStore.canUserAccessModule(card.module),
  ),
);

const modulesCounterText = computed(() => t('home_modules_counter'));

type StatusBadgeVariant = 'validated' | 'progress';

function getStatusIcon(moduleLink: Module): string {
  const state = timelineStore.itemStates[moduleLink];
  if (state === MODULE_STATES.Validated) return 'o_check_circle';
  if (state === MODULE_STATES.InProgress) return 'o_pending';
  return '';
}

function getStatusBadgeVariant(moduleLink: Module): StatusBadgeVariant | null {
  const state = timelineStore.itemStates[moduleLink];
  if (state === MODULE_STATES.Validated) return 'validated';
  if (state === MODULE_STATES.InProgress) return 'progress';
  return null;
}

function getStatusLabelKey(moduleLink: Module): string {
  const state = timelineStore.itemStates[moduleLink];
  if (state === MODULE_STATES.Validated) return 'module_status_validated';
  if (state === MODULE_STATES.InProgress) return 'module_status_in_progress';
  return '';
}
</script>

<template>
  <q-page class="page-grid">
    <q-card flat class="container">
      <h1 class="text-h2 q-mb-md">{{ $t('home_title') }}</h1>
      <p class="text-body1">
        {{ $t('home_intro_1_part_1')
        }}<a
          :href="$t('home_intro_1_link_url')"
          target="_blank"
          rel="noopener noreferrer"
          class="link"
          >{{ $t('home_intro_1_link_text') }}</a
        >{{ $t('home_intro_1_part_2') }}
      </p>
      <p class="text-body1">{{ $t('home_intro_2') }}</p>
      <p class="text-body1">{{ $t('home_intro_3') }}</p>
      <p class="text-body1">{{ $t('home_intro_4') }}</p>
      <p class="text-body1">
        {{ $t('home_intro_5_part_1')
        }}<a
          :href="$t('home_intro_5_link_url')"
          target="_blank"
          rel="noopener noreferrer"
          class="link"
          >{{ $t('home_intro_5_link_text') }}</a
        >{{ $t('home_intro_5_part_2')
        }}<a :href="$t('home_intro_5_contact_link_url')" class="link">{{
          $t('home_intro_5_contact_link_text')
        }}</a
        >{{ $t('home_intro_5_part_3') }}
      </p>
      <p class="text-body1 q-mb-none">{{ $t('home_intro_6') }}</p>
      <q-btn
        color="info"
        :label="$t('home_start_button')"
        unelevated
        no-caps
        size="md"
        class="text-weight-medium q-mt-xl"
        :to="{ name: 'module', params: { module: firstEditableModule } }"
        :disable="!firstEditableModule"
      />
    </q-card>

    <div class="grid-2-col">
      <q-card flat class="container">
        <h3 class="text-h4 text-weight-medium">
          {{ $t('home_results_title') }}
        </h3>
        <h3 class="text-h5 text-weight-medium text-secondary">
          {{ $t('home_results_subtitle', { year: currentYear }) }}
        </h3>
        <div class="flex justify-between items-end q-mt-xl">
          <q-btn
            color="info"
            :label="$t('home_results_btn')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
            :to="{ name: 'results' }"
          />
          <div class="column items-end">
            <p class="text-h1 text-weight-medium q-mb-none">
              {{ formatTonnesCO2(validatedTotals?.total_tonnes_co2eq) }}
            </p>
            <p class="text-secondary text-body2 q-mb-none">
              {{ $t('tco2eq') }}
            </p>
          </div>
        </div>
      </q-card>
      <q-card flat class="container column justify-between">
        <div class="row items-center justify-between q-mb-xl">
          <div class="row items-center q-gutter-sm">
            <q-icon name="o_notifications" color="info" size="md" />
            <h3 class="text-h4 text-weight-medium">
              {{ $t('calculator_update_title') }}
            </h3>
          </div>
          <span class="text-body2 text-secondary">
            {{ $t('calculator_update_last_update') }}
          </span>
        </div>
        <div>
          <h4 class="text-h5 text-weight-medium q-mb-xs">
            {{ $t('calculator_update_entry_title') }}
          </h4>
          <p class="text-body2 text-secondary q-mb-none">
            {{ $t('calculator_update_entry_body') }}
          </p>
        </div>
      </q-card>
    </div>

    <div>
      <div class="text-h5 text-weight-medium q-mb-sm">
        {{ modulesCounterText }}
      </div>
      <div class="grid-3-col">
        <q-card
          v-for="moduleCard in moduleCardsWithStatus"
          :key="moduleCard.module"
          flat
          class="container"
        >
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <ModuleIconBox
                :name="moduleCard.module"
                size="sm"
                class="q-mr-xs"
              />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(moduleCard.module) }}
              </h3>
            </div>
            <span
              v-if="getStatusBadgeVariant(moduleCard.module)"
              class="home-status-badge"
              :class="`home-status-badge--${getStatusBadgeVariant(moduleCard.module)}`"
            >
              <q-icon :name="getStatusIcon(moduleCard.module)" size="xs" />
              {{ $t(getStatusLabelKey(moduleCard.module)) }}
            </span>
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(`${moduleCard.module}-description`) }}
          </p>
          <q-separator class="grey-6 q-my-lg" />
          <div class="flex justify-between items-center">
            <div class="flex items-center">
              <q-btn
                v-if="
                  hasModulePermission(
                    moduleCard.module,
                    PermissionAction.VIEW,
                  ) &&
                  !hasModulePermission(moduleCard.module, PermissionAction.EDIT)
                "
                icon="o_visibility"
                :label="$t('home_view_btn')"
                unelevated
                no-caps
                size="sm"
                class="text-weight-medium btn-secondary q-mr-sm"
                :to="{ name: 'module', params: { module: moduleCard.module } }"
              />

              <q-btn
                icon="o_edit"
                :label="$t('home_edit_btn')"
                unelevated
                no-caps
                size="sm"
                class="text-weight-medium btn-secondary"
                :disable="
                  !hasModulePermission(
                    moduleCard.module,
                    PermissionAction.EDIT,
                  ) || moduleCard.isDisabled
                "
                :to="
                  hasModulePermission(
                    moduleCard.module,
                    PermissionAction.EDIT,
                  ) && !moduleCard.isDisabled
                    ? { name: 'module', params: { module: moduleCard.module } }
                    : undefined
                "
              >
                <q-tooltip v-if="moduleCard.isDisabled">
                  {{ $t('module_disabled') }}
                </q-tooltip>
              </q-btn>
            </div>
            <div
              v-if="
                timelineStore.itemStates[moduleCard.module] !==
                MODULE_STATES.Default
              "
              class="row q-gutter-xs text-body1 items-baseline"
            >
              <p class="text-weight-medium q-mb-none">
                {{
                  MODULES_CONFIG[moduleCard.module].totalFormatter(
                    moduleCardTotals[moduleCard.module],
                  )
                }}
              </p>
              <p class="text-body2 text-secondary q-mb-none">
                {{
                  $t('module_total_result_title_unit', {
                    type: moduleCard.module,
                  })
                }}
              </p>
            </div>
            <div
              v-else
              class="row q-gutter-xs text-body1 text-grey-4 items-baseline"
            >
              <p class="text-weight-medium q-mb-none">—</p>
            </div>
          </div>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.home-status-badge {
  display: inline-flex;
  align-items: center;
  gap: tokens.$home-status-badge-gap;
  font-size: tokens.$home-status-badge-font-size;
  font-weight: tokens.$home-status-badge-font-weight;
  line-height: 1;
  padding: tokens.$home-status-badge-padding-y
    tokens.$home-status-badge-padding-x;
  border-radius: tokens.$radius-pill;

  &--validated {
    background-color: rgba(
      var(--q-positive-rgb, 33, 186, 69),
      tokens.$home-status-badge-bg-opacity-validated
    );
    color: var(--q-positive);
  }

  &--progress {
    background-color: rgba(
      var(--q-warning-rgb, 242, 192, 56),
      tokens.$home-status-badge-bg-opacity-progress
    );
    color: var(--q-warning);
  }
}
</style>
