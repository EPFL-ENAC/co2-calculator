<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { ReportingStats } from 'src/api/reporting';
import { MODULE_STATES } from 'src/constant/moduleStates';

const { t } = useI18n();

interface Props {
  stats: ReportingStats;
}

defineProps<Props>();

const cards = computed(() => [
  {
    label: t('backoffice_reporting_usage_box_validated'),
    tooltipText: t('backoffice_reporting_usage_box_validated'),
    key: MODULE_STATES.Validated,
    color: '#28a745',
    icon: 'edit_note',
  },
  {
    label: t('backoffice_reporting_usage_box_in_progress'),
    tooltipText: t('backoffice_reporting_usage_box_in_progress'),
    key: MODULE_STATES.InProgress,
    color: '#ffc107',
    icon: 'hourglass_empty',
  },
  {
    label: t('backoffice_reporting_usage_box_not_started'),
    tooltipText: t('backoffice_reporting_usage_box_not_started'),
    key: MODULE_STATES.Default,
    color: '#8e8e8e',
    icon: 'hourglass_empty',
  },
]);
</script>

<template>
  <div class="reporting-stat-cards">
    <q-card
      v-for="card in cards"
      :key="card.key"
      flat
      bordered
      class="stat-card"
    >
      <q-card-section class="justify-between d-flex q-pa-none">
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{ card.label }}
        </span>
      </q-card-section>
      <q-card-section
        class="text-h1 text-weight-bold q-pa-none"
        :style="{ color: card.color }"
      >
        {{ stats[card.key].toLocaleString() }}
      </q-card-section>
    </q-card>
  </div>
</template>

<style scoped lang="scss">
.reporting-stat-cards {
  display: flex;
  flex-direction: row;
  gap: 18px;
}

.stat-card {
  flex: 1;
  margin-top: 24px;
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
