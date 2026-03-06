<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
const { t } = useI18n();

interface Props {
  stats: Record<string, number>;
  loading?: boolean;
}

defineProps<Props>();

// number of validated modules // if one unit
const cards = computed(() => [
  {
    label: t('backoffice_reporting_usage_box_one_unit'),
    tooltipText: t('backoffice_reporting_usage_box_one_unit'),
    key: 'total_entries',
    color: '#007480',
    icon: 'edit_note',
  },
]);
</script>

<template>
  <div class="reporting-stat-cards">
    <div v-for="card in cards" :key="card.key" class="stat-card">
      <div class="stat-card__header justify-between d-flex w-full">
        <!-- <q-icon :name="card.icon" :style="{ color: card.color }" size="24px" /> -->

        <div class="stat-card__label">
          {{ card.label }}
        </div>
        <q-icon
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer"
          :aria-label="$t('module-info-label')"
        />
        <q-tooltip anchor="center right" self="top right" class="u-tooltip">
          <div class="text-h5 text-weight-medium q-mb-sm">
            {{ card.tooltipText }}
          </div>
        </q-tooltip>
      </div>
      <div class="stat-card__value" :style="{ color: card.color }">
        <q-skeleton v-if="loading" type="text" width="80px" height="38px" />
        <template v-else>
          {{ stats[card.key].toLocaleString() }}
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.reporting-stat-cards {
  display: flex;
  flex-direction: row;
  gap: 18px;
  margin-top: 24px;
}

.stat-card {
  flex: 1;
  border: 1px solid #c1c1c1;
  border-radius: 3px;
  padding: 24px;
  height: 131px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: #ffffff;

  &__header {
    display: flex;
    align-items: center;
  }

  &__value {
    font-size: 38px;
    font-weight: 700;
    line-height: 1;
  }

  &__label {
    font-size: 18px;
    font-weight: 700;
    color: #000000;
  }
}
</style>
