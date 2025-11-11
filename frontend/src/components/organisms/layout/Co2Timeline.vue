<script setup lang="ts">
import { ref } from 'vue';
import { useTimelineStore } from 'src/stores/modules';
import Co2TimelineItem from 'src/components/molecules/Co2TimelineItem.vue';
import { TimelineItem } from 'src/types';
import { useRouter, useRoute } from 'vue-router';
import { timelineItems } from 'app/constant/timelineItems';

const timelineStore = useTimelineStore();

const selectedId = ref<number | null>(1);
const router = useRouter();
const route = useRoute();

const handleTimelineClick = (item: TimelineItem) => {
  selectedId.value = item.id;
  // Navigate to the correct module route
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
    class="timeline flex flex-row items-center relative q-pa-lg"
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
        width="150px"
        class="q-mt-none"
      />
    </template>
  </div>
</template>
