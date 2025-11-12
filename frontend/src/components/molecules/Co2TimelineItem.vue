<script setup lang="ts">
import { withDefaults, defineProps, computed } from 'vue';
import { ModuleState, TimelineItem } from 'src/types';

const props = withDefaults(
  defineProps<{
    currentState?: ModuleState;
    item: TimelineItem;
    handleClick?: (item: TimelineItem) => void;
    selected?: boolean;
  }>(),
  {
    currentState: 'default',
    selected: false,
  },
);

// Computed class for the dot
const textClass = (color: string) =>
  `absolute text-weight-medium text-no-wrap text-${color}`;

// Computed property for state color
const stateColor = computed(() => {
  switch (props.currentState) {
    case 'in-progress':
      return 'grey-6';
    case 'validated':
      return 'accent';
    default:
      return 'grey-5';
  }
});

// Button class logic moved to computed property
const btnClass = computed(() => {
  let base = textClass(stateColor.value) + '  q-mt-sm q-py-none';
  if (props.selected) {
    switch (props.currentState) {
      case 'validated':
        base += ' bg-accent text-white';
        break;
      case 'in-progress':
        base += ' bg-grey-3 text-white';
        break;
      default:
        base += ' bg-grey-2 text-white';
    }
  }
  return base;
});
</script>

<template>
  <div class="timeline-item-wrapper relative-position">
    <q-icon
      :color="stateColor"
      size="xs"
      :name="item.icon"
      class="absolute q-bottom-md"
      style="bottom: 30px; left: 50%; transform: translateX(-50%)"
    />
    <q-btn
      @click="() => props.handleClick && props.handleClick(props.item)"
      size="xs"
      :class="[
        'q-btn-timeline-item',
        `q-btn-timeline-item--${props.currentState}` +
          (props.selected ? ' q-btn-timeline-item__selected' : ''),
      ]"
    >
    </q-btn>
    <q-btn
      flat
      dense
      rounded
      no-caps
      size="sm"
      :class="btnClass"
      style="left: 50%; transform: translateX(-50%)"
      @click="() => props.handleClick && props.handleClick(props.item)"
      :label="$t(item.link)"
    />
  </div>
</template>
