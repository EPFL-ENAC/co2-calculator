<script setup lang="ts">
import type { AuditStats } from 'src/api/audit';

interface Props {
  stats: AuditStats;
  loading?: boolean;
}

defineProps<Props>();

const cards = [
  {
    label: 'TOTAL ENTRIES',
    key: 'total_entries' as keyof AuditStats,
    color: '#0D6EFD',
    icon: 'edit_note',
  },
  {
    label: 'CREATES',
    key: 'creates' as keyof AuditStats,
    color: '#28A745',
    icon: 'add_circle',
  },
  {
    label: 'UPDATES',
    key: 'updates' as keyof AuditStats,
    color: '#FFC107',
    icon: 'edit',
  },
  {
    label: 'DELETES',
    key: 'deletes' as keyof AuditStats,
    color: '#DC3545',
    icon: 'delete',
  },
];
</script>

<template>
  <div class="audit-stat-cards">
    <div v-for="card in cards" :key="card.key" class="stat-card">
      <div class="stat-card__header">
        <q-icon :name="card.icon" :style="{ color: card.color }" size="24px" />
      </div>
      <div class="stat-card__value" :style="{ color: card.color }">
        <q-skeleton v-if="loading" type="text" width="80px" height="38px" />
        <template v-else>
          {{ stats[card.key].toLocaleString() }}
        </template>
      </div>
      <div class="stat-card__label">{{ card.label }}</div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.audit-stat-cards {
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
