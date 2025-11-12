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
    timelineItems.find((item) => item.link === route.params.module)?.id ??
    timelineItems[0]?.id,
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
  <div
    class="timeline flex flex-row items-center relative q-py-lg"
    style="min-width: 1200px"
  >
    <template v-for="item in timelineItems" :key="item.id">
      <Co2TimelineItem
        :item="item"
        :currentState="timelineStore.itemStates[item.link]"
        :selected="selectedId === item.id"
        :handleClick="handleTimelineClick"
      />
      <q-separator
        v-if="item.id !== timelineItems[timelineItems.length - 1].id"
        class="timeline-separator q-mt-none bg-grey-5"
      />
    </template>
    <q-separator class="timeline-separator q-mt-none bg-grey-5" />
    <q-icon name="arrow_forward" color="grey-6" />
    <q-btn
      icon="o_bar_chart"
      color="red"
      :label="$t('results-btn')"
      unelevated
      no-caps
      size="md"
      class="text-weight-medium q-ml-xl"
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
