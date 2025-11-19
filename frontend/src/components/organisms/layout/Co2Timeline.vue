<script setup lang="ts">
import { useTimelineStore } from 'src/stores/modules';
import Co2TimelineItem from 'src/components/molecules/Co2TimelineItem.vue';
import { useRoute } from 'vue-router';
import { timelineItems } from 'src/constant/timelineItems';

const timelineStore = useTimelineStore();

const route = useRoute();
</script>
<template>
  <div class="timeline-container q-py-xl">
    <div class="timeline-grid">
      <template v-for="item in timelineItems" :key="item.link">
        <Co2TimelineItem
          :item="item"
          :currentState="timelineStore.itemStates[item.link]"
          :selected="route.params.module === item.link"
          :to="{
            name: 'module',
            params: { ...route.params, module: item.link },
          }"
        />
        <q-separator class="timeline-separator self-center bg-grey-5" />
      </template>

      <q-icon
        name="arrow_forward"
        color="grey-6"
        class="self-center timeline-arrow"
      />
      <q-btn
        icon="o_bar_chart"
        color="info"
        :label="$t('results_btn')"
        unelevated
        no-caps
        size="md"
        class="text-weight-medium self-center timeline-results-btn"
        :to="{ name: 'results', params: route.params }"
      />
    </div>
  </div>
</template>
