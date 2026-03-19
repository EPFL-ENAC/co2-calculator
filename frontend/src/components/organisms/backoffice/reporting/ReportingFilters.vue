<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useUnitFiltersStore } from 'src/stores/unitFilters';

const emit = defineEmits<{
  (
    e: 'update:filters',
    filters: {
      path_lvl2: number[];
      path_lvl3: number[];
      path_lvl4: number[];
      completion_status: number | string;
    },
  ): void;
}>();

const { t } = useI18n();
const unitFiltersStore = useUnitFiltersStore();

// Selected units for each level
const selectedLevel2Units = ref<number[]>([]);
const selectedLevel3Units = ref<number[]>([]);
const selectedLevel4Units = ref<number[]>([]);

const completion = ref('');

// Initialize with first page of data for each level
// unitFiltersStore.setSearchQueryLevel2('');
// unitFiltersStore.setSearchQueryLevel3('');
// unitFiltersStore.setSearchQueryLevel4('');

// LVL2: http://localhost:8000/api/v1/backoffice-reporting/units?level=2&unit_type_labels=Service%20central&unit_type_labels=Facult%C3%A9
// LVL3: http://localhost:8000/api/v1/backoffice-reporting/units?level=3&unit_type_label=Institut
// LVL4: http://localhost:8000/api/v1/backoffice-reporting/units?level=4&parent_unit_type_label=Institut

function handleFiltersChange() {
  emit('update:filters', {
    path_lvl2: selectedLevel2Units.value,
    path_lvl3: selectedLevel3Units.value,
    path_lvl4: selectedLevel4Units.value,
    completion_status: completion.value,
  });
}
</script>
<template>
  <div class="row q-mb-md">
    <div class="grid-4-col full-width">
      <!-- Error message display for Level 2 -->
      <q-banner
        v-if="unitFiltersStore.errorLevel2 !== null"
        dense
        class="bg-negative text-white q-mb-sm"
      >
        <template #avatar>
          <q-icon name="error" />
        </template>
        {{ $t('common_error_message') }}
        <template #action>
          <q-btn
            flat
            color="white"
            :label="$t('common_retry')"
            @click="unitFiltersStore.setSearchQueryLevel2('')"
          />
        </template>
      </q-banner>

      <!-- Level 2 Units Dropdown
       service central, faculté
       -->
      <q-select
        v-model="selectedLevel2Units"
        :options="unitFiltersStore.dataLevel2"
        option-value="value"
        option-label="label"
        multiple
        use-chips
        dense
        outlined
        use-input
        input-debounce="300"
        emit-value
        map-options
        :loading="unitFiltersStore.loadingLevel2"
        :label="`${$t('backoffice_reporting_filter_units_lvl2_label')}`"
        filled
        clearable
        class="full-width"
        @filter="unitFiltersStore.filterLevel2Units"
        @virtual-scroll="unitFiltersStore.onScrollLevel2"
        @update:model-value="handleFiltersChange"
      >
        <template #prepend>
          <q-icon name="o_business" color="grey-6" size="xs" />
        </template>
      </q-select>

      <!-- Error message display for Level 3 -->
      <q-banner
        v-if="unitFiltersStore.errorLevel3 !== null"
        dense
        class="bg-negative text-white q-mb-sm"
      >
        <template #avatar>
          <q-icon name="error" />
        </template>
        {{ $t('common_error_message') }}
        <template #action>
          <q-btn
            flat
            color="white"
            :label="$t('common_retry')"
            @click="unitFiltersStore.setSearchQueryLevel3('')"
          />
        </template>
      </q-banner>

      <!-- Level 3 Units Dropdown
       institut -->
      <q-select
        v-model="selectedLevel3Units"
        :options="unitFiltersStore.dataLevel3"
        option-value="value"
        option-label="label"
        multiple
        use-chips
        dense
        outlined
        use-input
        input-debounce="300"
        emit-value
        map-options
        :loading="unitFiltersStore.loadingLevel3"
        :label="`${$t('backoffice_reporting_filter_units_lvl3_label')}`"
        filled
        clearable
        class="full-width"
        @filter="unitFiltersStore.filterLevel3Units"
        @virtual-scroll="unitFiltersStore.onScrollLevel3"
        @update:model-value="handleFiltersChange"
      >
        <template #prepend>
          <q-icon name="o_business" color="grey-6" size="xs" />
        </template>
      </q-select>

      <!-- Error message display for Level 4 -->
      <q-banner
        v-if="unitFiltersStore.errorLevel4 !== null"
        dense
        class="bg-negative text-white q-mb-sm"
      >
        <template #avatar>
          <q-icon name="error" />
        </template>
        {{ $t('common_error_message') }}
        <template #action>
          <q-btn
            flat
            color="white"
            :label="$t('common_retry')"
            @click="unitFiltersStore.setSearchQueryLevel4('')"
          />
        </template>
      </q-banner>

      <!-- Level 4 Units Dropdown -->
      <q-select
        v-model="selectedLevel4Units"
        :options="unitFiltersStore.dataLevel4"
        option-value="value"
        option-label="label"
        multiple
        use-chips
        dense
        outlined
        use-input
        input-debounce="300"
        emit-value
        map-options
        :loading="unitFiltersStore.loadingLevel4"
        :label="`${$t('backoffice_reporting_filter_units_label')}`"
        filled
        clearable
        class="full-width"
        @filter="unitFiltersStore.filterLevel4Units"
        @virtual-scroll="unitFiltersStore.onScrollLevel4"
        @update:model-value="handleFiltersChange"
      >
        <template #prepend>
          <q-icon name="o_business" color="grey-6" size="xs" />
        </template>
      </q-select>

      <q-select
        v-model="completion"
        outlined
        dense
        :options="[
          { label: t('backoffice_reporting_csv_validated'), value: 2 },
          { label: t('backoffice_reporting_csv_in_progress'), value: 1 },
          { label: t('backoffice_reporting_csv_default'), value: 0 },
        ]"
        option-value="value"
        option-label="label"
        :label="$t('backoffice_reporting_row_completion_label')"
        class="full-width"
        style="flex-grow: 1"
        @update:model-value="handleFiltersChange"
      >
        <template #prepend>
          <q-icon name="o_check_small" color="grey-6" size="xs" />
        </template>
      </q-select>
    </div>
  </div>
</template>
