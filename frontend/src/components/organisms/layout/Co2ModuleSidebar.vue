<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth';
import { useTimelineStore, useModuleStore } from 'src/stores/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { PermissionAction } from 'src/stores/auth';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { timelineItems } from 'src/constant/timelineItems';
import { MODULES, type Module } from 'src/constant/modules';
import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';
import ModuleTotalResult from 'src/components/organisms/module/ModuleTotalResult.vue';
import ResultsFilterPanel from 'src/components/layout/ResultsFilterPanel.vue';
import { MODULES_CONFIG } from 'src/constant/module-config';
import type { ModuleConfig } from 'src/constant/moduleConfig';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const timelineStore = useTimelineStore();
const yearConfigStore = useYearConfigStore();

const collapsed = ref(false);

const moduleStore = useModuleStore();

const currentModule = computed(() => route.params.module as Module | undefined);

const currentModuleConfig = computed<ModuleConfig | undefined>(() =>
  currentModule.value
    ? (MODULES_CONFIG[currentModule.value] as ModuleConfig)
    : undefined,
);

const currentTotalResult = computed(() => {
  if (!currentModule.value) return undefined;
  if (currentModule.value === MODULES.Headcount) {
    return moduleStore.state.data?.totals?.total_annual_fte;
  }
  return moduleStore.state.data?.totals?.total_tonnes_co2eq;
});

const visibleItems = computed(() =>
  timelineItems.filter(
    (item) =>
      yearConfigStore.isModuleVisible(item.link as Module) &&
      authStore.canUserAccessModule(item.link as Module),
  ),
);

function getStatusColor(moduleLink: string): string {
  const state = timelineStore.itemStates[moduleLink as Module];
  if (state === MODULE_STATES.Validated) return 'positive';
  if (state === MODULE_STATES.InProgress) return 'warning';
  return '';
}

function getStatusIcon(moduleLink: string): string {
  const state = timelineStore.itemStates[moduleLink as Module];
  if (state === MODULE_STATES.Validated) return 'o_check_circle';
  if (state === MODULE_STATES.InProgress) return 'o_pending';
  return '';
}

function hasPermission(moduleLink: string): boolean {
  return authStore.hasUserModulePermission(
    moduleLink as Module,
    PermissionAction.EDIT,
  );
}

function isModuleSelected(moduleLink: string): boolean {
  return route.name === 'module' && route.params.module === moduleLink;
}

const isResultsSelected = computed(() => route.name === 'results');

const collapseToggleIcon = computed(() =>
  collapsed.value ? 'chevron_right' : 'chevron_left',
);

function navigateToModule(moduleLink: string) {
  if (!hasPermission(moduleLink)) return;
  router.push({
    name: 'module',
    params: { ...route.params, module: moduleLink },
  });
}

function navigateToResults() {
  router.push({ name: 'results', params: route.params });
}
</script>

<template>
  <div class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <div class="sidebar-toggle" @click="collapsed = !collapsed">
      <q-icon :name="collapseToggleIcon" size="xs" />
    </div>
    <ModuleTotalResult
      v-if="currentModule && currentModuleConfig"
      :type="currentModule"
      :data="currentTotalResult"
      :module-config="currentModuleConfig"
      sidebar
    />
    <q-list class="sidebar-items">
      <q-item
        v-for="item in visibleItems"
        :key="item.link"
        class="sidebar-item"
        :class="{ 'sidebar-item--selected': isModuleSelected(item.link) }"
        :disable="!hasPermission(item.link)"
        clickable
        @click="navigateToModule(item.link)"
      >
        <span class="icon-wrapper">
          <ModuleIconBox :name="item.link" size="md" />
          <!-- Collapsed: small dot at bottom-right of icon box -->
          <span
            v-if="getStatusColor(item.link) && collapsed"
            class="status-dot"
            :class="`bg-${getStatusColor(item.link)}`"
          />
        </span>
        <q-item-label
          class="sidebar-label text-body2"
          :class="{ 'sidebar-label--hidden': collapsed }"
          >{{ $t(item.link) }}</q-item-label
        >
        <!-- Expanded: status icon pushed to far right -->
        <q-icon
          v-if="getStatusColor(item.link) && !collapsed"
          :name="getStatusIcon(item.link)"
          :color="getStatusColor(item.link)"
          class="status-icon"
          size="xs"
        />
        <q-tooltip
          v-if="collapsed"
          anchor="center right"
          self="center left"
          :offset="[6, 0]"
          class="sidebar-tooltip"
        >
          {{ $t(item.link) }}
        </q-tooltip>
      </q-item>
      <q-separator />
      <q-item
        class="sidebar-item sidebar-results"
        :class="{ 'sidebar-results--selected': isResultsSelected }"
        clickable
        @click="navigateToResults"
      >
        <span class="sidebar-results__icon-box">
          <q-icon name="o_bar_chart" size="sm" class="sidebar-results__icon" />
        </span>
        <q-item-label
          class="sidebar-label sidebar-results__label text-body2"
          :class="{ 'sidebar-label--hidden': collapsed }"
          >{{ $t('results_btn') }}</q-item-label
        >
        <q-icon
          v-if="!collapsed"
          name="chevron_right"
          size="xs"
          class="sidebar-results__chevron status-icon"
        />
        <q-tooltip
          v-if="collapsed"
          anchor="center right"
          self="center left"
          :offset="[6, 0]"
          class="sidebar-tooltip"
        >
          {{ $t('results_btn') }}
        </q-tooltip>
      </q-item>
    </q-list>
    <q-separator v-if="isResultsSelected" />
    <ResultsFilterPanel v-if="isResultsSelected" :collapsed="collapsed" />
    <q-separator v-if="isResultsSelected" />
    <div class="sidebar-docs-wrapper">
      <q-separator />
      <q-item
        class="sidebar-item sidebar-docs"
        tag="a"
        :href="$t('header_user_documentation_link')"
        target="_blank"
        clickable
      >
        <span class="sidebar-docs__icon-box">
          <q-icon name="o_article" size="sm" class="sidebar-docs__icon" />
        </span>
        <q-item-label
          class="sidebar-label text-body2"
          :class="{ 'sidebar-label--hidden': collapsed }"
          >{{ $t('documentation_button_label') }}</q-item-label
        >
        <q-tooltip
          v-if="collapsed"
          anchor="center right"
          self="center left"
          :offset="[6, 0]"
          class="sidebar-tooltip"
        >
          {{ $t('documentation_button_label') }}
        </q-tooltip>
      </q-item>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.sidebar {
  height: 100%;
  width: 20rem;
  background-color: white;
  border-right: tokens.$sidebar-border-width solid tokens.$sidebar-border-color;
  transition: width 0.2s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  &--collapsed {
    width: 4rem;

    .sidebar-toggle {
      justify-content: center;
      padding: tokens.$sidebar-padding-y 0;
    }

    .sidebar-item {
      justify-content: center;
      padding: 0.5rem 0;
    }

    // Swap full panel for mini view when collapsed
    :deep(.mtr-sidebar__body) {
      display: none;
    }
    :deep(.mtr-sidebar__mini) {
      display: flex;
    }
  }
}

.sidebar-items {
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-toggle {
  padding: tokens.$sidebar-padding-y tokens.$sidebar-padding-left;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  cursor: pointer;
  background-color: white;
  border-bottom: tokens.$sidebar-border-width solid tokens.$sidebar-border-color;
  flex-shrink: 0;

  &:hover {
    background-color: #e8e8e8;
  }
}

.sidebar-item {
  // Gap lives on the label's margin-left so it transitions away cleanly.
  gap: 0;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;

  padding: 0.5rem 0 0.5rem 0.5rem;
  cursor: pointer;
  min-width: 0;

  &:hover,
  &--selected {
    background-color: #e8e8e8;
  }
}

// Positions the floating badge relative to the icon box, not the full item.
.icon-wrapper {
  position: relative;
  display: inline-flex;
  flex-shrink: 0;
}

// Label gap + width + opacity all transition together so the icon never
// has to reposition — it stays left-aligned as the label shrinks away.
.sidebar-label {
  margin-left: tokens.$sidebar-item-gap;
  max-width: 200px;
  padding-left: 0.5rem;
  overflow: hidden;
  white-space: nowrap;
  opacity: 1;
  pointer-events: auto;
  transition:
    opacity 0.2s ease,
    max-width 0.2s ease,
    margin-left 0.2s ease;

  &--hidden {
    opacity: 0;
    max-width: 0;
    margin-left: 0;
    pointer-events: none;
  }
}

// Collapsed state: small colored dot anchored to bottom-right of icon box.
.status-dot {
  position: absolute;
  bottom: -3px;
  right: -3px;
  width: 0.8rem;
  height: 0.8rem;
  border-radius: 50%;
  border: 2px solid white;
  flex-shrink: 0;
}

.status-icon {
  margin-left: auto;
  flex-shrink: 0;
  margin-right: 1rem;
}

.sidebar-docs-wrapper {
  margin-top: auto;
  flex-shrink: 0;
}

.sidebar-docs {
  &__icon-box {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    border-radius: 8px;
    border: 1.5px solid tokens.$sidebar-border-color;
    background-color: tokens.$module-result-bg;
    flex-shrink: 0;
  }

  &__icon {
    color: tokens.$color-text-muted;
  }
}

.sidebar-results {
  &:hover,
  &--selected {
    background-color: tokens.$module-result-bg-validated !important;
  }

  &__icon-box {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    border-radius: 8px;
    border: 1.5px solid tokens.$color-validated;
    background-color: tokens.$module-result-bg-validated;
    flex-shrink: 0;
  }

  &__icon {
    color: tokens.$color-validated;
  }

  &__label {
    color: tokens.$color-validated;
    font-weight: tokens.$text-weight-medium;
  }

  &__chevron {
    color: tokens.$color-validated;
  }
}
</style>
