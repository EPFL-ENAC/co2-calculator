<script setup lang="ts">
import type { AuditLogEntry, AuditAction } from 'src/api/audit';

interface Props {
  rows: AuditLogEntry[];
  loading?: boolean;
  sortBy: string;
  sortDesc: boolean;
}

defineProps<Props>();
const emit = defineEmits<{
  sort: [column: string];
  view: [id: number];
  copy: [entry: AuditLogEntry];
}>();

const columns = [
  { key: 'change_type', label: 'Action', sortable: true },
  { key: 'entity_type', label: 'Entity Type', sortable: true },
  { key: 'entity_id', label: 'Entity ID', sortable: true },
  { key: 'changed_at', label: 'Timestamp', sortable: true },
  { key: 'changed_by', label: 'User', sortable: true },
  { key: 'handler_id', label: 'Handler ID', sortable: false },
  { key: 'message_summary', label: 'Summary', sortable: false },
  { key: 'actions', label: 'Actions', sortable: false },
];

const actionColors: Record<AuditAction, string> = {
  CREATE: '#28A745',
  READ: '#0D6EFD',
  UPDATE: '#FFC107',
  DELETE: '#DC3545',
  ROLLBACK: '#6C757D',
  TRANSFER: '#17A2B8',
};

function getActionColor(action: AuditAction): string {
  return actionColors[action] || '#6C757D';
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('en-GB', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function truncate(text: string | null, max = 80): string {
  if (!text) return '';
  return text.length > max ? text.slice(0, max - 3) + '...' : text;
}

function getUserLabel(row: AuditLogEntry): string {
  if (row.changed_by_display_name) {
    return row.changed_by_display_name;
  }
  if (row.handler_id === 'csv_ingestion') {
    return `JobId: ${row.entity_id}`;
  }
  if (row.entity_type === 'DataIngestionJob') {
    return `JobId: ${row.entity_id}`;
  }
  if (row.changed_by !== null && row.changed_by !== undefined) {
    return String(row.changed_by);
  }
  return 'Unknown';
}
</script>

<template>
  <div class="audit-table">
    <!-- Header -->
    <div class="audit-table__header">
      <div
        v-for="col in columns"
        :key="col.key"
        class="audit-table__header-cell"
        :class="{
          'audit-table__header-cell--sortable': col.sortable,
          'audit-table__header-cell--action': col.key === 'change_type',
          'audit-table__header-cell--entity-type': col.key === 'entity_type',
          'audit-table__header-cell--entity-id': col.key === 'entity_id',
          'audit-table__header-cell--actions': col.key === 'actions',
        }"
        @click="col.sortable ? emit('sort', col.key) : undefined"
      >
        {{ col.label }}
        <q-icon
          v-if="col.sortable"
          :name="
            sortBy === col.key
              ? sortDesc
                ? 'arrow_drop_down'
                : 'arrow_drop_up'
              : 'unfold_more'
          "
          size="14px"
          class="sort-icon"
        />
      </div>
    </div>

    <!-- Loading skeleton -->
    <template v-if="loading">
      <div
        v-for="i in 5"
        :key="i"
        class="audit-table__row audit-table__row--skeleton"
      >
        <div v-for="col in columns" :key="col.key" class="audit-table__cell">
          <q-skeleton type="text" width="80%" />
        </div>
      </div>
    </template>

    <!-- Empty state -->
    <div v-else-if="rows?.length === 0" class="audit-table__empty">
      <q-icon name="search_off" size="48px" color="grey-6" />
      <p class="text-h6 text-grey-7 q-mt-sm q-mb-none">
        No audit entries found
      </p>
      <p class="text-body2 text-grey-6">
        Try adjusting your filters or search query.
      </p>
    </div>

    <!-- Data rows -->
    <template v-else>
      <div v-for="row in rows" :key="row.id" class="audit-table__row">
        <!-- Action -->
        <div class="audit-table__cell audit-table__cell--action">
          <span
            class="status-dot"
            :style="{ backgroundColor: getActionColor(row.change_type) }"
          />
          <span
            class="action-text"
            :style="{ color: getActionColor(row.change_type) }"
          >
            {{ row.change_type }}
          </span>
        </div>

        <!-- Entity Type -->
        <div class="audit-table__cell audit-table__cell--entity-type">
          {{ row.entity_type }}
        </div>

        <!-- Entity ID -->
        <div class="audit-table__cell audit-table__cell--entity-id">
          {{ row.entity_id }}
        </div>

        <!-- Timestamp -->
        <div class="audit-table__cell">
          {{ formatTimestamp(row.changed_at) }}
        </div>

        <!-- User -->
        <div class="audit-table__cell">
          {{ getUserLabel(row) }}
        </div>

        <!-- Handler ID -->
        <div class="audit-table__cell">
          {{ row.handler_id || '-' }}
        </div>

        <!-- Summary -->
        <div
          class="audit-table__cell audit-table__cell--summary"
          :style="{ color: getActionColor(row.change_type) }"
        >
          {{ truncate(row.message_summary) }}
        </div>

        <!-- Actions -->
        <div class="audit-table__cell audit-table__cell--actions">
          <button class="action-link" @click="emit('view', row.id)">
            View
          </button>
          <button class="action-link" @click="emit('copy', row)">Copy</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.audit-table {
  border: 1px solid #c1c1c1;
  border-radius: 3px;
  background: #ffffff;
  overflow: hidden;

  &__header {
    display: flex;
    height: 42px;
    border-bottom: 1px solid #c1c1c1;
    padding: 0 12px;
    align-items: center;
    gap: 12px;

    &-cell {
      flex: 1;
      font-weight: 700;
      font-size: 14px;
      color: #212121;
      display: flex;
      align-items: center;
      gap: 4px;
      user-select: none;

      &--sortable {
        cursor: pointer;

        &:hover {
          color: #0d6efd;
        }
      }

      &--actions {
        text-align: right;
        justify-content: flex-end;
        flex: 0.6;
      }

      .sort-icon {
        opacity: 0.6;
      }
    }
  }

  &__row {
    display: flex;
    min-height: 26px;
    background: #212121;
    padding: 4px 12px;
    align-items: center;
    gap: 12px;
    font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
    font-size: 12px;
    line-height: 18px;
    color: #ffffff;

    &:hover {
      background: #2a2a2a;
    }

    &--skeleton {
      background: #f5f5f5;
    }
  }

  &__cell {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 6px;

    &--action,
    &--entity-type,
    &--entity-id {
      flex: 0 1 100px;
      max-width: 100px;
    }

    &--summary {
      flex: 1.5;
    }

    &--actions {
      flex: 0.6;
      justify-content: flex-end;
      gap: 8px;
    }
  }

  &__empty {
    padding: 48px 24px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
}

.audit-table__header-cell--action,
.audit-table__header-cell--entity-type,
.audit-table__header-cell--entity-id {
  flex: 0 1 100px;
  max-width: 100px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.action-text {
  font-weight: 700;
}

.action-link {
  background: none;
  border: none;
  color: #ffffff;
  cursor: pointer;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  text-decoration: underline;
  padding: 0;

  &:hover {
    color: #0d6efd;
  }
}
</style>
