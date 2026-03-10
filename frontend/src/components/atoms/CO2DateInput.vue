<template>
  <q-input
    v-model="formModel"
    bordered
    mask="####/##/##"
    :rules="getDateRules()"
    :label="label"
    :error="!!errors"
    :error-message="errors"
    :required="field.required"
    :dense="true"
    :outlined="true"
    :disable="disabled"
  >
    <template #append>
      <q-icon name="o_event" class="cursor-pointer">
        <q-popup-proxy cover transition-show="scale" transition-hide="scale">
          <q-date
            v-model="formModel"
            :min="yearDateRange.min"
            :max="yearDateRange.max"
            :navigation-min-year-month="yearDateRange.navigationMin"
            :navigation-max-year-month="yearDateRange.navigationMax"
          >
            <div class="row items-center justify-end">
              <q-btn v-close-popup label="Close" color="primary" flat />
            </div>
          </q-date>
        </q-popup-proxy>
      </q-icon>
    </template>
  </q-input>
</template>

<script lang="ts" setup>
import { computed } from 'vue';
import { QInput, QIcon } from 'quasar';
import type { ModuleField } from 'src/constant/moduleConfig';
import type { AllSubmoduleTypes, Module } from 'src/constant/modules';
import { useI18n } from 'vue-i18n';

const { t: $t } = useI18n();

const props = defineProps<{
  modelValue: string | null;
  moduleType: Module | string;
  submoduleType: AllSubmoduleTypes;
  field: ModuleField;
  entry: Record<string, unknown>;
  selectedYear: string | number;
  loading?: boolean;
  errors?: string | null | undefined;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void;
}>();

const formModel = computed({
  get() {
    return props.modelValue;
  },
  set(value: string | null) {
    emit('update:modelValue', value);
  },
});

const label = computed(() =>
  $t(`${props.field.labelKey || props.field.label}`, {
    submoduleTitle: $t(`${props.moduleType}-${props.submoduleType}`),
  }),
);

const yearDateRange = computed(() => ({
  min: `${props.selectedYear}/01/01`,
  max: `${props.selectedYear}/12/31`,
  navigationMin: `${props.selectedYear}/01`,
  navigationMax: `${props.selectedYear}/12`,
  default: `${props.selectedYear}/01/01`,
}));

function getDateRules() {
  const required = props.field.required;
  const dateFormatRule = (val: string) => {
    if (!val || val === '') return required ? 'Required' : true;
    return /^\d{4}[/.]\d{2}[/.]\d{2}$/.test(val) || 'Invalid date format';
  };
  return [dateFormatRule];
}
</script>
