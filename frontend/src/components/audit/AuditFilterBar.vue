<script setup lang="ts">
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { AuditAction } from 'src/api/audit';

const { t } = useI18n();

interface Props {
  action: AuditAction | null;
  entityType: string | null;
  module: string | null;
  handlerId: string | null;
  dateRange: { from: string; to: string } | null;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'update:action': [value: AuditAction | null];
  'update:entityType': [value: string | null];
  'update:module': [value: string | null];
  'update:handlerId': [value: string | null];
  'update:dateRange': [value: { from: string; to: string } | null];
  'filter-change': [];
}>();

const actionOptions = computed(() => [
  { label: t('audit_filter_all_actions'), value: null },
  { label: t('audit_action_create'), value: 'CREATE' },
  { label: t('audit_action_read'), value: 'READ' },
  { label: t('audit_action_update'), value: 'UPDATE' },
  { label: t('audit_action_delete'), value: 'DELETE' },
  { label: t('audit_action_rollback'), value: 'ROLLBACK' },
  { label: t('audit_action_transfer'), value: 'TRANSFER' },
]);

const entityTypeOptions = computed(() => [
  { label: t('audit_filter_all_entities'), value: null },
  { label: t('audit_entity_data_entry'), value: 'DataEntry' },
  { label: t('audit_entity_data_ingestion_job'), value: 'DataIngestionJob' },
  { label: t('audit_entity_user'), value: 'User' },
  { label: t('audit_entity_factor'), value: 'Factor' },
  {
    label: t('audit_entity_data_entry_read'),
    value: 'DataEntryReadByCarbonReportModule',
  },
  { label: t('audit_entity_emission_factor'), value: 'EmissionFactor' },
]);

const moduleOptions = computed(() => [
  { label: t('audit_filter_all_modules'), value: null },
  { label: t('audit_module_headcount'), value: 'headcount' },
  {
    label: t('audit_module_professional_travel'),
    value: 'professional_travel',
  },
  { label: t('audit_module_infrastructure'), value: 'infrastructure' },
  {
    label: t('audit_module_equipment_electric'),
    value: 'equipment_electric_consumption',
  },
  { label: t('audit_module_purchase'), value: 'purchase' },
  { label: t('audit_module_internal_services'), value: 'internal_services' },
  { label: t('audit_module_external_cloud'), value: 'external_cloud_and_ai' },
]);

const datePresetOptions = computed(() => [
  { label: t('audit_date_all_time'), value: null },
  { label: t('audit_date_today'), value: 'today' },
  { label: t('audit_date_last_7_days'), value: '7days' },
  { label: t('audit_date_last_30_days'), value: '30days' },
  { label: t('audit_date_custom_range'), value: 'custom' },
]);

const showDatePicker = computed(() => datePresetValue.value === 'custom');

const datePresetValue = ref<string | null>(props.dateRange ? 'custom' : null);
const customDateFrom = ref<string>(props.dateRange?.from || '');
const customDateTo = ref<string>(props.dateRange?.to || '');

function onActionChange(val: AuditAction | null) {
  emit('update:action', val);
  emit('filter-change');
}

function onEntityTypeChange(val: string | null) {
  emit('update:entityType', val);
  emit('filter-change');
}

function onModuleChange(val: string | null) {
  emit('update:module', val);
  emit('filter-change');
}

function onHandlerIdChange(val: string | number | null) {
  const nextValue = val ? String(val).trim() : null;
  emit('update:handlerId', nextValue);
  emit('filter-change');
}

function onDatePresetChange(val: string | null) {
  if (val === 'custom') {
    return; // wait for date picker
  }

  const now = new Date();
  let range: { from: string; to: string } | null = null;

  if (val === 'today') {
    const today = now.toISOString().slice(0, 10);
    range = { from: `${today}T00:00:00Z`, to: `${today}T23:59:59Z` };
  } else if (val === '7days') {
    const to = now.toISOString();
    const from = new Date(
      now.getTime() - 7 * 24 * 60 * 60 * 1000,
    ).toISOString();
    range = { from, to };
  } else if (val === '30days') {
    const to = now.toISOString();
    const from = new Date(
      now.getTime() - 30 * 24 * 60 * 60 * 1000,
    ).toISOString();
    range = { from, to };
  }

  emit('update:dateRange', range);
  emit('filter-change');
}

function onCustomDateApply() {
  if (customDateFrom.value && customDateTo.value) {
    emit('update:dateRange', {
      from: `${customDateFrom.value}T00:00:00Z`,
      to: `${customDateTo.value}T23:59:59Z`,
    });
    emit('filter-change');
  }
}
</script>

<template>
  <div class="audit-filter-bar">
    <q-select
      :model-value="action"
      :options="actionOptions"
      emit-value
      map-options
      dense
      outlined
      class="filter-dropdown"
      @update:model-value="onActionChange"
    >
      <template #prepend>
        <q-icon name="manufacturing" size="18px" color="grey-7" />
      </template>
    </q-select>

    <q-select
      :model-value="entityType"
      :options="entityTypeOptions"
      emit-value
      map-options
      dense
      outlined
      class="filter-dropdown"
      @update:model-value="onEntityTypeChange"
    >
      <template #prepend>
        <q-icon name="category" size="18px" color="grey-7" />
      </template>
    </q-select>

    <q-select
      :model-value="module"
      :options="moduleOptions"
      emit-value
      map-options
      dense
      outlined
      class="filter-dropdown"
      @update:model-value="onModuleChange"
    >
      <template #prepend>
        <q-icon name="view_module" size="18px" color="grey-7" />
      </template>
    </q-select>

    <q-input
      :model-value="handlerId || ''"
      dense
      outlined
      clearable
      class="filter-dropdown"
      :label="t('audit_label_handler_id')"
      @update:model-value="onHandlerIdChange"
    >
      <template #prepend>
        <q-icon name="badge" size="18px" color="grey-7" />
      </template>
    </q-input>

    <q-select
      v-model="datePresetValue"
      :options="datePresetOptions"
      emit-value
      map-options
      dense
      outlined
      class="filter-dropdown"
      @update:model-value="onDatePresetChange"
    >
      <template #prepend>
        <q-icon name="calendar_today" size="18px" color="grey-7" />
      </template>
    </q-select>

    <!-- Custom date range picker -->
    <div v-if="showDatePicker" class="custom-date-range">
      <q-input
        v-model="customDateFrom"
        dense
        outlined
        type="date"
        :label="t('audit_label_from')"
        class="date-input"
      />
      <q-input
        v-model="customDateTo"
        dense
        outlined
        type="date"
        :label="t('audit_label_to')"
        class="date-input"
      />
      <q-btn
        dense
        flat
        color="primary"
        :label="t('audit_btn_apply')"
        @click="onCustomDateApply"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.audit-filter-bar {
  display: flex;
  flex-direction: row;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.filter-dropdown {
  flex: 1;
  min-width: 180px;
  max-width: 280px;
}

.custom-date-range {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;

  .date-input {
    max-width: 200px;
  }
}
</style>
