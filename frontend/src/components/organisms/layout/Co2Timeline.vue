<script setup lang="ts">
import { computed } from 'vue';
import { useTimelineStore } from 'src/stores/modules';
import Co2TimelineItem from 'src/components/molecules/Co2TimelineItem.vue';
import { TimelineItem } from 'src/types';
import { useRouter, useRoute } from 'vue-router';
import { timelineItems } from 'src/constant/timelineItems';

const timelineStore = useTimelineStore();

const router = useRouter();
const route = useRoute();

const selectedId = computed(
  () =>
    timelineItems.find((item) => item.link === route.params.module)?.link ??
    timelineItems[0]?.link,
);

const handleTimelineClick = (item: TimelineItem) => {
  router.push({
    name: 'module',
    params: {
      language: route.params.language || 'en',
      unit: route.params.unit,
      year: route.params.year,
      module: item.link,
    },
  });
};
</script>
<template>
  <div class="timeline-grid q-py-xl">
    <template v-for="(item, index) in timelineItems" :key="item.link">
      <Co2TimelineItem
        :item="item"
        :currentState="timelineStore.itemStates[item.link]"
        :selected="selectedId === item.link"
        :handleClick="handleTimelineClick"
      />
      <q-separator
        v-if="index !== timelineItems.length - 1"
        class="timeline-separator self-center bg-grey-5"
      />
    </template>
    <q-separator class="timeline-separator self-center bg-grey-5" />
    <q-icon name="arrow_forward" color="grey-6" class="self-center" />
    <q-btn
      icon="o_bar_chart"
      color="red"
      :label="$t('results-btn')"
      unelevated
      no-caps
      size="md"
      class="text-weight-medium self-center q-ml-lg"
      @click="
        router.push({
          name: 'results',
          params: {
            language: route.params.language || 'en',
            unit: route.params.unit,
            year: route.params.year,
          },
        })
      "
    />
  </div>
</template>
