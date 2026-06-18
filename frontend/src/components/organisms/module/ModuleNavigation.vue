<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { Module, MODULES_LIST } from 'src/constant/modules';
import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';
import { useTimelineStore } from 'src/stores/modules';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useAuthStore } from 'src/stores/auth';

const props = defineProps<{
  currentModule: Module;
}>();

const $route = useRoute();
const timelineStore = useTimelineStore();
const yearConfigStore = useYearConfigStore();
const authStore = useAuthStore();

const visibleModulesList = computed(() =>
  MODULES_LIST.filter(
    (m) =>
      yearConfigStore.isModuleVisible(m) && authStore.canUserAccessModule(m),
  ),
);

const currentIndex = computed(() => {
  return visibleModulesList.value.indexOf(props.currentModule);
});

const isLastModule = computed(() => {
  return currentIndex.value === visibleModulesList.value.length - 1;
});

const previousModule = computed(() => {
  if (currentIndex.value > 0) {
    return visibleModulesList.value[currentIndex.value - 1];
  }
  return null;
});

const nextModule = computed(() => {
  if (currentIndex.value < visibleModulesList.value.length - 1) {
    return visibleModulesList.value[currentIndex.value + 1];
  }
  return null;
});

const previousModuleRoute = computed(() => {
  if (!previousModule.value) return null;
  return {
    name: 'module',
    params: {
      language: $route.params.language,
      unit: $route.params.unit,
      year: $route.params.year,
      module: previousModule.value,
    },
  };
});

const nextModuleRoute = computed(() => {
  if (!nextModule.value) return null;
  return {
    name: 'module',
    params: {
      language: $route.params.language,
      unit: $route.params.unit,
      year: $route.params.year,
      module: nextModule.value,
    },
  };
});

// Build route for results page
const resultsRoute = computed(() => {
  return {
    name: 'results',
    params: {
      language: $route.params.language,
      unit: $route.params.unit,
      year: $route.params.year,
    },
  };
});

const canValidateCurrentModule = computed(() =>
  authStore.hasUserCanValidateModuleStatus(),
);

function validateCurrentModule() {
  if (!canValidateCurrentModule.value) return;
  timelineStore.setState(props.currentModule, MODULE_STATES.Validated);
}
</script>

<template>
  <div class="module-navigation">
    <router-link
      v-if="previousModule"
      :to="previousModuleRoute"
      class="module-navigation__link module-navigation__link--previous"
      @click="validateCurrentModule"
    >
      <q-icon name="chevron_left" class="chevron-left" size="sm" />

      <span class="text-body2 text-weight-medium">{{
        $t(previousModule!)
      }}</span>
      <module-icon-box :name="previousModule" size="sm" />
    </router-link>
    <router-link
      v-if="nextModule"
      :to="nextModuleRoute"
      class="module-navigation__link module-navigation__link--next"
      @click="validateCurrentModule"
    >
      <module-icon-box :name="nextModule" size="sm" />
      <span class="text-body2 text-weight-medium">{{ $t(nextModule!) }}</span>
      <q-icon name="chevron_right" class="chevron-right" size="sm" />
    </router-link>
    <router-link
      v-if="isLastModule"
      :to="resultsRoute"
      class="module-navigation__link module-navigation__link--next module-navigation__link--results"
      @click="validateCurrentModule"
    >
      <span class="results-icon-box">
        <q-icon name="bar_chart" size="sm" />
      </span>
      <span class="text-body2 text-weight-medium">{{ $t('results_btn') }}</span>
    </router-link>
  </div>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-navigation {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  width: tokens.$layout-page-width;
  margin: 0 auto;

  &__link {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
    color: inherit;

    transition: background-color 0.2s;

    &:hover {
      .chevron-left {
        transform: translateX(-0.25rem);
      }
      .chevron-right {
        transform: translateX(0.25rem);
      }
    }

    &--previous {
      margin-right: auto;
    }

    &--results {
      color: tokens.$color-validated;
    }

    .chevron-left {
      transition: transform 0.2s;
    }
    .chevron-right {
      transition: transform 0.2s;
    }
  }
}

.results-icon-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: tokens.$module-icon-box-size-sm;
  height: tokens.$module-icon-box-size-sm;
  border-radius: tokens.$module-icon-box-border-radius;
  border: tokens.$module-icon-box-border-width solid tokens.$color-validated;
  background-color: tokens.$module-result-bg-validated;
  flex-shrink: 0;
}
</style>
