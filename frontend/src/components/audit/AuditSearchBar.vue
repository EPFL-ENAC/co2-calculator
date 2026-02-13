<script setup lang="ts">
import { ref } from 'vue';

interface Props {
  modelValue: string;
}

defineProps<Props>();
const emit = defineEmits<{
  'update:modelValue': [value: string];
  search: [];
  export: [format: 'csv' | 'json'];
}>();

const showExportMenu = ref(false);

function onInput(val: string) {
  emit('update:modelValue', val);
}

function onSearch() {
  emit('search');
}

function onExport(format: 'csv' | 'json') {
  showExportMenu.value = false;
  emit('export', format);
}
</script>

<template>
  <div class="audit-search-bar">
    <div class="search-input-wrapper">
      <q-icon name="search" size="20px" color="grey-7" class="search-icon" />
      <input
        :value="modelValue"
        type="text"
        placeholder="Search by user, entity, or reason..."
        class="search-input"
        @input="onInput(($event.target as HTMLInputElement).value)"
        @keyup.enter="onSearch"
      />
    </div>
    <div class="search-actions">
      <q-btn
        flat
        dense
        no-caps
        icon="download"
        color="grey-7"
        class="export-btn"
      >
        <q-menu>
          <q-list dense>
            <q-item v-close-popup clickable @click="onExport('csv')">
              <q-item-section>Export as CSV</q-item-section>
            </q-item>
            <q-item v-close-popup clickable @click="onExport('json')">
              <q-item-section>Export as JSON</q-item-section>
            </q-item>
          </q-list>
        </q-menu>
      </q-btn>
      <q-btn
        no-caps
        unelevated
        label="Search"
        class="search-btn"
        @click="onSearch"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.audit-search-bar {
  display: flex;
  flex-direction: row;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;

  .search-icon {
    position: absolute;
    left: 10px;
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    height: 40px;
    border: 1px solid #c1c1c1;
    border-radius: 3px;
    padding: 8px 10px 8px 36px;
    font-size: 14px;
    font-weight: 500;
    outline: none;

    &::placeholder {
      color: #707070;
      font-weight: 500;
    }

    &:focus {
      border-color: #0d6efd;
    }
  }
}

.search-actions {
  display: flex;
  gap: 8px;
  align-items: center;

  .search-btn {
    background: #ff0000;
    color: #ffffff;
    height: 40px;
    padding: 2px 16px;
  }

  .export-btn {
    height: 40px;
  }
}
</style>
