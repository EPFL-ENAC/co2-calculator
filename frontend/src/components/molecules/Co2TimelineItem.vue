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

const stateColor = computed(() => {
  switch (props.currentState) {
    case 'in-progress':
      return 'grey-6';
    case 'validated':
      return 'accent';
    default:
      return 'grey-4';
  }
});

// Computed class for the dot
const textClass = (color: string) =>
  `absolute text-weight-medium text-no-wrap text-${color}`;
</script>

<template>
  <div class="timeline-item-wrapper relative-position" style="width: 24px">
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
      no-caps
      size="sm"
      :class="
        textClass(stateColor) +
        (props.selected
          ? ' q-btn-timeline-item__selected  bg-accent  text-white q-mt-xs'
          : '  q-mt-xs') +
        ' q-py-xs'
      "
      style="left: 50%; transform: translateX(-50%)"
      @click="() => props.handleClick && props.handleClick(props.item)"
      :label="item.label"
      :to="item.link ? { name: item.link } : undefined"
      role="link"
    />
  </div>
</template>
