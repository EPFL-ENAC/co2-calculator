<script setup lang="ts">
import { computed } from 'vue';
import { TimelineItem } from 'src/constant/timelineItems';
import { ModuleState } from 'src/constant/moduleStates';
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
    currentState: 'default',
    to: '/',
    selected: false,
  },
);

// Computed property for state color
const stateColor = computed(() => {
  switch (props.currentState) {
    case 'in-progress':
      return 'grey-6';
    case 'validated':
      return 'info';
    default:
      return 'grey-5';
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
        `q-btn-timeline-item--${currentState}`,
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
          'bg-info text-white': selected && currentState === 'validated',
          'bg-grey-3 text-white': selected && currentState === 'in-progress',
          'bg-grey-2 text-white': selected && currentState === 'default',
        },
      ]"
      :label="$t(item.link)"
    />
  </div>
</template>
