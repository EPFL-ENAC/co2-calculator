<script setup lang="ts">
import { computed } from 'vue';
import { TimelineItem } from 'src/constant/timelineItems';
import { ModuleState, MODULE_STATES } from 'src/constant/moduleStates';
import { RouteLocationRaw } from 'vue-router';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

const props = withDefaults(
  defineProps<{
    currentState?: ModuleState;
    item: TimelineItem;
    to?: RouteLocationRaw;
    selected?: boolean;
  }>(),
  {
    currentState: MODULE_STATES.Default,
    to: '/',
    selected: false,
  },
);

// Computed property for state color
const stateColor = computed(() => {
  switch (props.currentState) {
    case MODULE_STATES.InProgress:
      return 'grey-6';
    case MODULE_STATES.Validated:
      return 'info';
    default:
      return 'grey-5';
  }
});

const stateColorString = computed(() => {
  switch (props.currentState) {
    case MODULE_STATES.InProgress:
      return 'in-progress';
    case MODULE_STATES.Validated:
      return 'validated';
    default:
      return 'default';
  }
});
</script>

<template>
  <div class="timeline-item-wrapper column items-center justify-between">
    <module-icon :name="item.link" size="md" :color="stateColor" />
    <q-btn
      :to="to"
      size="xs"
      :class="[
        'q-btn-timeline-item',
        `q-btn-timeline-item--${stateColorString}`,
        {
          'q-btn-timeline-item__selected': selected,
        },
      ]"
    >
    </q-btn>
    <q-btn
      flat
      dense
      rounded
      no-caps
      size="sm"
      :to="to"
      class="text-weight-medium text-no-wrap q-py-none"
      :class="[
        `text-${stateColor}`,
        {
          'bg-info text-white':
            selected && currentState === MODULE_STATES.Validated,
          'bg-grey-3 text-white':
            selected && currentState === MODULE_STATES.InProgress,
          'bg-grey-2 text-white':
            selected && currentState === MODULE_STATES.Default,
        },
      ]"
      :label="$t(item.link)"
    />
  </div>
</template>
