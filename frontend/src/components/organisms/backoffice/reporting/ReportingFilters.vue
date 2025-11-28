<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps<{
  affiliations: string[];
  units: string[];
}>();

const emit = defineEmits<{
  (
    e: 'update:filters',
    filters: {
      affiliation: string[];
      units: string[];
      completion: string;
      outlier_values: boolean | null;
      search: string;
    },
  ): void;
}>();

const affiliation = ref<string[]>([]);
const currentUnits = ref<string[]>([]);
const completion = ref('');

const affiliationOptions = computed(() =>
  props.affiliations.map((aff) => ({ label: aff, value: aff })),
);

const unitOptions = computed(() =>
  props.units.map((unit) => ({ label: unit, value: unit })),
);

const filteredUnitOptions = ref<Array<{ label: string; value: string }>>([]);

// Initialize filtered options with all options
watch(
  unitOptions,
  (newOptions) => {
    filteredUnitOptions.value = newOptions;
  },
  { immediate: true },
);

function filterUnits(val: string, update: (callback: () => void) => void) {
  if (val === '') {
    update(() => {
      filteredUnitOptions.value = unitOptions.value;
    });
    return;
  }

  update(() => {
    const needle = val.toLowerCase();
    filteredUnitOptions.value = unitOptions.value.filter(
      (v) => v.label.toLowerCase().indexOf(needle) > -1,
    );
  });
}

const search = ref('');

const outlier_values = ref<boolean | null>(null);

function extractValue<T>(value: T | null | undefined, defaultValue: T): T {
  if (value === null || value === undefined) {
    return defaultValue;
  }
  if (typeof value === 'object' && 'value' in value) {
    return (value as { value: T }).value ?? defaultValue;
  }
  return value;
}

watch(
  [affiliation, currentUnits, completion, outlier_values, search],
  ([newAffiliation, newUnits, newCompletion, newOutlierValues, newSearch]) => {
    // Backend handles validation and filtering, so just pass the values directly
    const affiliationValue = Array.isArray(newAffiliation)
      ? newAffiliation
      : [];
    const unitsValue = Array.isArray(newUnits) ? newUnits : [];
    const completionValue = extractValue(newCompletion, '');
    const outlierValuesResult = extractValue(
      newOutlierValues,
      null as boolean | null,
    );

    emit('update:filters', {
      affiliation: affiliationValue,
      units: unitsValue,
      completion: String(completionValue),
      outlier_values: outlierValuesResult,
      search: String(newSearch || ''),
    });
  },
  { immediate: true },
);
</script>
<template>
  <div class="row q-mb-md">
    <div class="grid-4-col full-width">
      <q-select
        v-model="currentUnits"
        :options="filteredUnitOptions"
        option-value="value"
        option-label="label"
        multiple
        use-chips
        dense
        outlined
        use-input
        input-debounce="0"
        emit-value
        map-options
        :label="$t('backoffice_reporting_row_units_label')"
        class="full-width"
        @filter="filterUnits"
      >
        <template #prepend>
          <q-icon name="o_business" color="grey-6" size="xs" />
        </template>
      </q-select>
      <q-select
        v-model="affiliation"
        :options="affiliationOptions"
        option-value="value"
        option-label="label"
        multiple
        use-chips
        outlined
        dense
        emit-value
        map-options
        :label="$t('backoffice_reporting_row_affiliation_label')"
        class="full-width"
        style="flex-grow: 1"
      >
        <template #prepend>
          <q-icon name="o_school" color="grey-6" size="xs" />
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
      <q-select
        v-model="outlier_values"
        outlined
        dense
        :options="[
          { label: t('common_filter_all'), value: null },
          { label: t('common_filter_yes'), value: true },
          { label: t('common_filter_no'), value: false },
        ]"
        option-value="value"
        option-label="label"
        :label="$t('backoffice_reporting_row_outlier_values_label')"
        class="full-width"
        style="flex-grow: 1"
      >
        <template #prepend>
          <q-icon name="o_report" color="grey-6" size="xs" />
        </template>
      </q-select>
    </div>
  </div>
  <q-input
    v-model="search"
    outlined
    dense
    type="search"
    color="text-grey-6"
    :label="$t('common_filters_search_label')"
    class="text-weight-medium"
  >
    <template #prepend>
      <q-icon name="o_search" color="grey-6" size="xs" />
    </template>
  </q-input>
</template>
