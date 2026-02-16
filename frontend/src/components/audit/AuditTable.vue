<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { AuditLogEntry, AuditAction } from 'src/api/audit';

const { t, d: $d } = useI18n();

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
  { key: 'change_type', label: t('audit_col_action'), sortable: true },
  { key: 'entity_type', label: t('audit_col_entity_type'), sortable: true },
  { key: 'entity_id', label: t('audit_col_entity_id'), sortable: true },
  { key: 'changed_at', label: t('audit_col_timestamp'), sortable: true },
  { key: 'changed_by', label: t('audit_col_user'), sortable: true },
  { key: 'handler_id', label: t('audit_col_handler_id'), sortable: false },
  { key: 'message_summary', label: t('audit_col_summary'), sortable: false },
  { key: 'actions', label: t('audit_col_actions'), sortable: false },
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

function truncate(text: string | null, max = 80): string {
  if (!text) return '';
  return text.length > max ? text.slice(0, max - 3) + '...' : text;
}

function getUserLabel(row: AuditLogEntry): string {
  if (row.changed_by_display_name) {
    return row.changed_by_display_name;
  }
  if (row.handler_id === 'csv_ingestion') {
    return t('audit_user_job_id', { id: row.changed_by });
  }
  if (row.entity_type === 'DataIngestionJob') {
    return t('audit_user_job_id', { id: row.entity_id });
  }
  if (row.changed_by !== null && row.changed_by !== undefined) {
    return String(row.handler_id);
  }
  return t('audit_user_unknown');
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
          [`audit-table__header-cell--${col.key}`]: true,
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
        {{ t('audit_no_entries_found') }}
      </p>
      <p class="text-body2 text-grey-6">
        {{ t('audit_adjust_filters') }}
      </p>
    </div>

    <!-- Data rows -->
    <template v-else>
      <div v-for="row in rows" :key="row.id" class="audit-table__row">
        <!-- Action -->
        <div class="audit-table__cell audit-table__cell--change_type">
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
        <div class="audit-table__cell audit-table__cell--entity_type">
          {{ row.entity_type }}
        </div>

        <!-- Entity ID -->
        <div :class="`audit-table__cell audit-table__cell--entity_id`">
          {{ row.entity_id }}
        </div>

        <!-- Timestamp -->
        <div class="audit-table__cell audit-table__cell--changed_at">
          {{ $d(new Date(row.changed_at), 'long') }}
        </div>

        <!-- User -->
        <div class="audit-table__cell audit-table__cell--changed_by">
          {{ getUserLabel(row) }}
        </div>

        <!-- Handler ID -->
        <div class="audit-table__cell audit-table__cell--handler_id">
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
            {{ t('audit_btn_view') }}
          </button>
          <button class="action-link" @click="emit('copy', row)">
            {{ t('audit_btn_copy') }}
          </button>
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
    gap: 3px;

    &--change_type,
    &--entity_type,
    &--entity_id,
    &--handler_id {
      flex: 0 1 70px;
      max-width: 70px;
    }

    &--changed_at {
      flex: 0 1 150px;
      max-width: 150px;
    }
    &--changed_by {
      flex: 0 1 250px;
      max-width: 250px;
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

.audit-table__header-cell--change_type,
.audit-table__header-cell--entity_type,
.audit-table__header-cell--handler_id,
.audit-table__header-cell--entity_id {
  flex: 0 1 70px;
  max-width: 70px;
}

.audit-table__header-cell--changed_at {
  flex: 0 1 150px;
  max-width: 150px;
}
.audit-table__header-cell--changed_by {
  flex: 0 1 250px;
  max-width: 250px;
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
