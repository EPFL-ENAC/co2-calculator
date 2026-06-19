<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useUnitFiltersStore } from 'src/stores/unitFilters';

const emit = defineEmits<{
  (
    e: 'update:filters',
    filters: {
      path_affiliation: number[];
      path_lvl4: number[];
      overall_status: number | string | undefined;
    },
  ): void;
}>();

const { t } = useI18n();
const unitFiltersStore = useUnitFiltersStore();

// Selected affiliation units (merged Lvl2 + Lvl3)
const selectedAffiliationUnits = ref<number[]>([]);
const selectedLevel4Units = ref<number[]>([]);

const completion = ref('');

function handleFiltersChange() {
  // Clear store search queries when filters are empty
  if (
    !selectedAffiliationUnits.value ||
    selectedAffiliationUnits.value.length === 0
  ) {
    unitFiltersStore.setSearchQueryAffiliation('');
  }
  if (!selectedLevel4Units.value || selectedLevel4Units.value.length === 0) {
    unitFiltersStore.setSearchQueryLevel4('');
  }

  // Emit filter update
  emit('update:filters', {
    path_affiliation: selectedAffiliationUnits.value || [],
    path_lvl4: selectedLevel4Units.value || [],
    overall_status: completion.value ?? undefined,
  });
}
</script>
<template>
  <div class="row q-mb-md">
    <div class="grid-3-col full-width">
      <!-- Error message display for Affiliation -->
      <q-banner
        v-if="unitFiltersStore.errorAffiliation !== null"
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
            @click="unitFiltersStore.setSearchQueryAffiliation('')"
          />
        </template>
      </q-banner>

      <!-- Affiliation Units Dropdown (merged Lvl2 + Lvl3)
       Facultés, Services centraux, Instituts
       -->
      <q-select
        v-model="selectedAffiliationUnits"
        :options="unitFiltersStore.dataAffiliation"
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
        :loading="unitFiltersStore.loadingAffiliation"
        :label="`${$t('backoffice_reporting_filter_affiliation_label')}`"
        filled
        clearable
        class="full-width"
        @filter="unitFiltersStore.filterAffiliationUnits"
        @virtual-scroll="unitFiltersStore.onScrollAffiliation"
        @update:model-value="handleFiltersChange"
        @clear="unitFiltersStore.setSearchQueryAffiliation('')"
      >
        <template #prepend>
          <q-icon name="o_business" color="grey-6" size="xs" />
        </template>
        <template #option="scope">
          <q-item v-bind="scope.itemProps">
            <q-item-section avatar>
              <q-icon name="o_business" color="grey-6" size="xs" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ scope.opt.label }}</q-item-label>
              <q-item-label caption>
                {{ scope.opt.unit_type_label }}
              </q-item-label>
            </q-item-section>
          </q-item>
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
        @clear="unitFiltersStore.setSearchQueryLevel4('')"
      >
        <template #prepend>
          <q-icon name="o_business" color="grey-6" size="xs" />
        </template>
      </q-select>

      <q-select
        v-model="completion"
        outlined
        dense
        clearable
        :options="[
          {
            label: t('backoffice_reporting_filter_completion_not_started'),
            value: 0,
          },
          {
            label: t('backoffice_reporting_filter_completion_in_progress'),
            value: 1,
          },
          {
            label: t('backoffice_reporting_filter_completion_completed'),
            value: 2,
          },
        ]"
        option-value="value"
        option-label="label"
        emit-value
        map-options
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
