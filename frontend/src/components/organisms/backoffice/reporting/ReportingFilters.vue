<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useUnitFiltersStore } from 'src/stores/unitFilters';

const { t } = useI18n();
const unitFiltersStore = useUnitFiltersStore();

const currentUnits = ref<number[]>([]);
const completion = ref('');

// Initialize with first page of data
// unitFiltersStore.setSearchQuery('');
</script>
<template>
  <div class="row q-mb-md">
    <div class="grid-4-col full-width">
      <!-- Error message display -->
      <q-banner
        v-if="unitFiltersStore.error !== null"
        dense
        class="bg-negative text-white q-mb-sm"
      >
        <template #avatar>
          <q-icon name="error" />
        </template>
        <!-- use error from AsyncResult -->
        {{ $t('common_error_message') }}
        <template #action>
          <q-btn
            flat
            color="white"
            :label="$t('common_retry')"
            @click="unitFiltersStore.setSearchQuery('')"
          />
        </template>
      </q-banner>

      <q-select
        v-model="currentUnits"
        :options="unitFiltersStore.data"
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
        :loading="unitFiltersStore.loading"
        :label="$t('backoffice_reporting_filter_units_label')"
        filled
        clearable
        class="full-width"
        @filter="unitFiltersStore.filterUnits"
        @virtual-scroll="unitFiltersStore.onScroll"
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
          { label: t('common_filter_all'), value: '' },
          { label: t('common_filter_complete'), value: 'complete' },
          { label: t('common_filter_incomplete'), value: 'incomplete' },
        ]"
        option-value="value"
        option-label="label"
        :label="$t('backoffice_reporting_row_completion_label')"
        class="full-width"
        style="flex-grow: 1"
      >
        <template #prepend>
          <q-icon name="o_check_small" color="grey-6" size="xs" />
        </template>
      </q-select>
    </div>
  </div>
</template>
