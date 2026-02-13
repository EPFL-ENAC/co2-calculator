<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES } from 'src/constant/modules';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import type { ModuleCard } from 'src/constant/moduleCards';
import {
  getBadgeForStatus,
  getModuleTypeId,
  MODULE_STATES,
} from 'src/constant/moduleStates';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useAuthStore } from 'src/stores/auth';
import { hasPermission, getModulePermissionPath } from 'src/utils/permission';
import { PermissionAction } from 'src/constant/permissions';
import type { Module } from 'src/constant/modules';
import { useTimelineStore } from 'src/stores/modules';
import { useModuleStore } from 'src/stores/modules';
import { nOrDash } from 'src/utils/number';

const { t } = useI18n();
const workspaceStore = useWorkspaceStore();
const authStore = useAuthStore();
const moduleStore = useModuleStore();

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

/**
 * Get the display total for a module card.
 * Headcount shows total_fte, other modules show total_tonnes_co2eq.
 */
function getModuleCardTotal(module: Module): number | null {
  const totals = validatedTotals.value;
  if (!totals) return null;
  const typeId = getModuleTypeId(module);
  const entry = totals.modules.find((m) => m.module_type_id === typeId);
  if (!entry) return null;
  if (module === MODULES.Headcount) {
    return entry.total_fte ?? null;
  }
  return entry.total_tonnes_co2eq ?? null;
}

function hasModulePermission(
  module: Module,
  action: PermissionAction,
): boolean {
  return hasPermission(
    authStore.user?.permissions,
    getModulePermissionPath(module),
    action,
  );
}
const timelineStore = useTimelineStore();

const moduleCardsWithStatus = computed(() => {
  return MODULE_CARDS.map(
    (card): ModuleCard => ({
      ...card,
      badge:
        getBadgeForStatus(timelineStore.itemStates[card.module]) ?? undefined,
    }),
  );
});

const modulesCounterText = computed(() =>
  t('home_modules_counter', {
    count: Object.keys(MODULES).length + 1,
  }),
);
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
        color="accent"
        :label="$t('home_start_button')"
        unelevated
        no-caps
        size="md"
        class="text-weight-medium q-mt-xl"
        :to="{ name: 'module', params: { module: MODULES.Headcount } }"
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
            color="accent"
            :label="$t('home_results_btn')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
            :to="{ name: 'results' }"
          />
          <div class="column items-end">
            <p class="text-h1 text-weight-medium q-mb-none">
              {{ nOrDash(validatedTotals?.total_tonnes_co2eq) }}
            </p>
            <p class="text-secondary text-body2 q-mb-none">
              {{ $t('tco2eq') }}
            </p>
          </div>
        </div>
      </q-card>
      <q-card flat class="container">
        <h3 class="text-h4 text-weight-medium">
          {{ $t('home_simulations_title') }}
        </h3>
        <h3 class="text-h5 text-weight-medium text-secondary">
          {{ $t('home_simulations_subtitle') }}
        </h3>
        <div class="flex justify-between items-end q-mt-xl">
          <q-btn
            color="accent"
            :label="$t('home_simulations_btn')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
            :to="{ name: 'simulations' }"
          />
          <div class="column items-end">
            <p class="text-h1 text-weight-medium q-mb-none">3</p>
            <p class="text-secondary text-body2 q-mb-none">
              {{ $t('home_simulations_units') }}
            </p>
          </div>
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
              <module-icon :name="moduleCard.module" size="md" color="accent" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(moduleCard.module) }}
              </h3>
            </div>
            <q-badge
              v-if="moduleCard.badge"
              rounded
              :color="moduleCard.badge.color"
              :text-color="moduleCard.badge.textColor"
              :class="moduleCard.badge.color === 'accent' ? 'q-pa-sm' : ''"
              :label="$t(moduleCard.badge.label)"
            />
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
                  !hasModulePermission(moduleCard.module, PermissionAction.EDIT)
                "
                :to="
                  hasModulePermission(moduleCard.module, PermissionAction.EDIT)
                    ? { name: 'module', params: { module: moduleCard.module } }
                    : undefined
                "
              />
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
                  nOrDash(getModuleCardTotal(moduleCard.module), {
                    options: {
                      maximumFractionDigits:
                        moduleCard.module === MODULES.Headcount ? 1 : 0,
                    },
                  })
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
