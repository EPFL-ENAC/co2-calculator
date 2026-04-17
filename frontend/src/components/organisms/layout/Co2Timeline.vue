<script setup lang="ts">
import { computed } from 'vue';
import { useTimelineStore } from 'src/stores/modules';
import Co2TimelineItem from 'src/components/molecules/Co2TimelineItem.vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from 'src/stores/auth';
import { hasPermission, getModulePermissionPath } from 'src/utils/permission';
import { PermissionAction } from 'src/constant/permissions';
import type { Module } from 'src/constant/modules';
import { timelineItems } from 'src/constant/timelineItems';
import { useYearConfigStore } from 'src/stores/yearConfig';

const timelineStore = useTimelineStore();
const authStore = useAuthStore();
const route = useRoute();
const yearConfigStore = useYearConfigStore();

function hasModulePermission(
  module: Module,
  action: PermissionAction,
): boolean {
  return hasPermission(
    authStore.user?.permissions,
    getModulePermissionPath(module),
    action,
  );
}

const visibleTimelineItems = computed(() => {
  return timelineItems.filter((item) =>
    yearConfigStore.isModuleVisible(item.link as Module),
  );
});
</script>
<template>
  <div class="timeline-container q-py-xl">
    <div class="timeline-grid">
      <template v-if="visibleTimelineItems.length === 0">
        <div class="text-center q-pa-xl">
          <q-icon name="block" size="64px" color="grey-5" class="q-mb-md" />
          <div class="text-h6">{{ $t('all_modules_disabled_title') }}</div>
          <div class="text-body2 text-secondary">
            {{ $t('all_modules_disabled_description') }}
          </div>
        </div>
      </template>
      <template v-else>
        <template
          v-for="(item, index) in visibleTimelineItems"
          :key="item.link"
        >
          <Co2TimelineItem
            :item="item"
            :current-state="timelineStore.itemStates[item.link]"
            :selected="route.params.module === item.link"
            :to="
              hasModulePermission(item.link, PermissionAction.EDIT)
                ? {
                    name: 'module',
                    params: { ...route.params, module: item.link },
                  }
                : undefined
            "
          />
          <q-separator
            v-if="index < visibleTimelineItems.length - 1"
            class="timeline-separator separator self-center bg-grey-5"
          />
        </template>

        <q-icon
          name="arrow_forward"
          color="grey-6"
          class="self-center timeline-arrow separator"
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
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.separator {
  margin-top: 12px;
}
</style>
