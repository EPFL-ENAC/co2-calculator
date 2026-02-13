<script setup lang="ts">
import { computed } from 'vue';
import type { AuditLogDetail, AuditAction } from 'src/api/audit';

interface Props {
  modelValue: boolean;
  entry: AuditLogDetail | null;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  copy: [entry: AuditLogDetail];
}>();

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
  return new Date(iso).toLocaleString('en-GB', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

const hasDiff = computed(() => {
  if (!props.entry?.data_diff) return false;
  const diff = props.entry.data_diff;
  return (
    Object.keys(diff.added || {}).length > 0 ||
    Object.keys(diff.removed || {}).length > 0 ||
    Object.keys(diff.changed || {}).length > 0
  );
});

function close() {
  emit('update:modelValue', false);
}

function onCopy() {
  if (props.entry) {
    emit('copy', props.entry);
  }
}

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return 'null';
  if (typeof val === 'object') return JSON.stringify(val, null, 2);
  return String(val);
}
</script>

<template>
  <q-dialog
    :model-value="modelValue"
    position="right"
    maximized
    @update:model-value="emit('update:modelValue', $event)"
  >
    <q-card v-if="entry" class="audit-detail-drawer">
      <!-- Header -->
      <q-card-section class="drawer-header">
        <div class="header-top">
          <div class="header-action">
            <span
              class="status-dot"
              :style="{ backgroundColor: getActionColor(entry.change_type) }"
            />
            <span
              class="action-label"
              :style="{ color: getActionColor(entry.change_type) }"
            >
              {{ entry.change_type }}
            </span>
          </div>
          <span class="timestamp">{{ formatTimestamp(entry.changed_at) }}</span>
        </div>
        <q-btn flat round dense icon="close" class="close-btn" @click="close" />
      </q-card-section>

      <q-separator />

      <!-- Metadata -->
      <q-card-section class="metadata-section">
        <h6 class="section-title">Metadata</h6>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Entity Type</span>
            <span class="meta-value">{{ entry.entity_type }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Entity ID</span>
            <span class="meta-value">{{ entry.entity_id }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Version</span>
            <span class="meta-value">{{ entry.version }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">User</span>
            <span class="meta-value">
              {{
                entry.changed_by_display_name || (entry.changed_by ?? 'Unknown')
              }}
            </span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Handler ID</span>
            <span class="meta-value">{{ entry.handler_id }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">IP Address</span>
            <span class="meta-value">{{ entry.ip_address }}</span>
          </div>
          <div v-if="entry.route_path" class="meta-item">
            <span class="meta-label">Route</span>
            <span class="meta-value">{{ entry.route_path }}</span>
          </div>
          <div v-if="entry.change_reason" class="meta-item meta-item--full">
            <span class="meta-label">Reason</span>
            <span class="meta-value">{{ entry.change_reason }}</span>
          </div>
          <div
            v-if="entry.handled_ids.length > 0"
            class="meta-item meta-item--full"
          >
            <span class="meta-label">Handled IDs</span>
            <span class="meta-value">{{ entry.handled_ids.join(', ') }}</span>
          </div>
        </div>
      </q-card-section>

      <q-separator />

      <!-- Diff viewer -->
      <q-card-section v-if="hasDiff" class="diff-section">
        <h6 class="section-title">Changes</h6>

        <!-- Changed fields -->
        <div
          v-if="
            entry.data_diff?.changed &&
            Object.keys(entry.data_diff.changed).length > 0
          "
        >
          <div
            v-for="(val, key) in entry.data_diff.changed"
            :key="'changed-' + key"
            class="diff-item"
          >
            <span class="diff-key">{{ key }}</span>
            <div class="diff-values">
              <div class="diff-old">
                <span class="diff-label">Before:</span>
                <code>{{ formatValue(val.old) }}</code>
              </div>
              <span class="diff-arrow">→</span>
              <div class="diff-new">
                <span class="diff-label">After:</span>
                <code>{{ formatValue(val.new) }}</code>
              </div>
            </div>
          </div>
        </div>

        <!-- Added fields -->
        <div
          v-if="
            entry.data_diff?.added &&
            Object.keys(entry.data_diff.added).length > 0
          "
        >
          <div class="diff-group-label text-positive">+ Added</div>
          <div
            v-for="(val, key) in entry.data_diff.added"
            :key="'added-' + key"
            class="diff-item diff-item--added"
          >
            <span class="diff-key">{{ key }}</span>
            <code>{{ formatValue(val) }}</code>
          </div>
        </div>

        <!-- Removed fields -->
        <div
          v-if="
            entry.data_diff?.removed &&
            Object.keys(entry.data_diff.removed).length > 0
          "
        >
          <div class="diff-group-label text-negative">- Removed</div>
          <div
            v-for="(val, key) in entry.data_diff.removed"
            :key="'removed-' + key"
            class="diff-item diff-item--removed"
          >
            <span class="diff-key">{{ key }}</span>
            <code>{{ formatValue(val) }}</code>
          </div>
        </div>
      </q-card-section>

      <q-separator />

      <!-- Full snapshot (collapsible) -->
      <q-card-section class="snapshot-section">
        <q-expansion-item
          label="Full Data Snapshot"
          header-class="section-title"
          dense
        >
          <pre class="snapshot-json">{{
            JSON.stringify(entry.data_snapshot, null, 2)
          }}</pre>
        </q-expansion-item>
      </q-card-section>

      <!-- Footer -->
      <q-card-actions align="right" class="drawer-footer">
        <q-btn
          flat
          no-caps
          label="Copy JSON"
          icon="content_copy"
          @click="onCopy"
        />
        <q-btn flat no-caps label="Close" @click="close" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped lang="scss">
.audit-detail-drawer {
  width: 550px;
  max-width: 90vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px;

  .header-top {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .header-action {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .action-label {
    font-size: 18px;
    font-weight: 700;
  }

  .timestamp {
    font-size: 14px;
    color: #707070;
  }

  .close-btn {
    position: absolute;
    top: 12px;
    right: 12px;
  }
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  color: #212121;
  margin: 0 0 12px 0;
}

.metadata-section {
  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;

    &--full {
      grid-column: 1 / -1;
    }
  }

  .meta-label {
    font-size: 12px;
    color: #707070;
    font-weight: 600;
    text-transform: uppercase;
  }

  .meta-value {
    font-size: 14px;
    color: #212121;
    word-break: break-all;
  }
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.diff-section {
  overflow-y: auto;
  flex: 1;

  .diff-item {
    margin-bottom: 12px;
    padding: 8px;
    background: #f5f5f5;
    border-radius: 4px;

    &--added {
      border-left: 3px solid #28a745;
    }

    &--removed {
      border-left: 3px solid #dc3545;
    }
  }

  .diff-key {
    font-weight: 700;
    font-size: 13px;
    color: #212121;
    display: block;
    margin-bottom: 4px;
  }

  .diff-values {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }

  .diff-old,
  .diff-new {
    flex: 1;

    .diff-label {
      font-size: 11px;
      color: #707070;
      display: block;
    }

    code {
      font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
      font-size: 12px;
      background: #212121;
      color: #ffffff;
      padding: 4px 8px;
      border-radius: 3px;
      display: block;
      white-space: pre-wrap;
      word-break: break-all;
    }
  }

  .diff-arrow {
    color: #707070;
    font-size: 16px;
    margin-top: 14px;
  }

  .diff-group-label {
    font-size: 13px;
    font-weight: 700;
    margin: 8px 0 4px;
  }
}

.snapshot-section {
  .snapshot-json {
    font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
    font-size: 12px;
    line-height: 18px;
    background: #212121;
    color: #ffffff;
    padding: 12px;
    border-radius: 3px;
    overflow-x: auto;
    max-height: 300px;
    margin: 0;
  }
}

.drawer-footer {
  border-top: 1px solid #c1c1c1;
  padding: 12px;
}
</style>
