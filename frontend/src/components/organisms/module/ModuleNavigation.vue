<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { Module, MODULES_LIST } from 'src/constant/modules';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { useTimelineStore } from 'src/stores/modules';
import { MODULE_STATES } from 'src/constant/moduleStates';

const props = defineProps<{
  currentModule: Module;
}>();

const $route = useRoute();
const timelineStore = useTimelineStore();

const currentIndex = computed(() => {
  return MODULES_LIST.indexOf(props.currentModule);
});

const isLastModule = computed(() => {
  return currentIndex.value === MODULES_LIST.length - 1;
});

const previousModule = computed(() => {
  if (currentIndex.value > 0) {
    return MODULES_LIST[currentIndex.value - 1];
  }
  return null;
});

const nextModule = computed(() => {
  if (currentIndex.value < MODULES_LIST.length - 1) {
    return MODULES_LIST[currentIndex.value + 1];
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

// Validate current module when navigating away
function validateCurrentModule() {
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
      <module-icon :name="previousModule" />
    </router-link>
    <router-link
      v-if="nextModule"
      :to="nextModuleRoute"
      class="module-navigation__link module-navigation__link--next"
      @click="validateCurrentModule"
    >
      <module-icon :name="nextModule" />
      <span class="text-body2 text-weight-medium">{{ $t(nextModule!) }}</span>
      <q-icon name="chevron_right" class="chevron-right" size="sm" />
    </router-link>
    <q-btn
      v-if="isLastModule"
      :to="resultsRoute"
      class="module-navigation__link module-navigation__link--next text-weight-medium"
      icon="bar_chart"
      :label="$t('results_btn')"
      color="info"
      unelevated
      no-caps
      size="md"
      @click="validateCurrentModule"
    >
    </q-btn>
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

    .chevron-left {
      transition: transform 0.2s;
    }
    .chevron-right {
      transition: transform 0.2s;
    }
  }
}
</style>
