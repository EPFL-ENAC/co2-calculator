<template>
  <div>
    <q-form
      ref="formRef"
      class="student-fte-calculator q-mx-md"
      @submit="onSubmit"
      @reset="onReset"
    >
      <q-input
        ref="studentsRef"
        v-model.number="students"
        type="number"
        :label="$t('student_helper_students_label')"
        :min="0"
        :rules="studentsRules"
        outlined
        dense
      />
      <q-input
        ref="durationRef"
        v-model.number="duration"
        type="number"
        :label="$t('student_helper_duration_label')"
        :min="0"
        :max="12"
        :rules="durationRules"
        outlined
        dense
      />
      <q-input
        ref="avgFTERef"
        v-model.number="avgFTE"
        type="number"
        :label="$t('student_helper_avg_fte_label')"
        :min="0"
        :max="1"
        :step="0.01"
        :rules="avgFTERules"
        outlined
        dense
      />

      <div class="calculated-result flex justify-between items-center">
        <div>
          <span class="text-body2 text-secondary"
            >{{ $t('student_helper_calculated_label') }}:</span
          >
          <div class="text-body1 text-weight-bold text-primary">
            {{ formattedCalculatedFTE }}
          </div>
        </div>

        <q-btn
          color="accent"
          :label="$t('student_helper_use_button')"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          type="submit"
        />
      </div>
    </q-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import type { QForm } from 'quasar';

const { t: $t } = useI18n();

const students = ref<number | null>(null);
const duration = ref<number | null>(null);
const avgFTE = ref<number | null>(null);

const formRef = ref<QForm | null>(null);

const emit = defineEmits<{
  (e: 'use-value', value: number): void;
}>();

const calculatedFTE = computed(() => {
  if (!students.value || !duration.value || !avgFTE.value) {
    return 0;
  }
  return (students.value * duration.value * avgFTE.value) / 12;
});

const formattedCalculatedFTE = computed(() => {
  if (calculatedFTE.value === 0) {
    return '-';
  }
  return calculatedFTE.value.toFixed(1);
});

// Validation rules
const studentsRules = computed(() => [
  (val: number | null) =>
    (val !== null && val > 0) ||
    $t('app_headcount_student_helper_students_error'),
]);
const durationRules = computed(() => [
  (val: number | null) =>
    (val !== null && val > 0 && val <= 12) ||
    $t('app_headcount_student_helper_duration_error'),
]);
const avgFTERules = computed(() => [
  (val: number | null) =>
    (val !== null && val > 0 && val <= 1) ||
    $t('app_headcount_student_helper_avg_fte_error'),
]);

function onReset() {
  students.value = null;
  duration.value = null;
  avgFTE.value = null;
  nextTick(() => {
    formRef.value?.resetValidation();
  });
}

async function onSubmit() {
  const valid = await formRef.value?.validate();
  if (!valid) return;
  emit('use-value', Number(calculatedFTE.value.toFixed(1)));
  onReset();
}
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.student-fte-calculator {
  display: flex;
  flex-direction: column;
  gap: tokens.$spacing-md;
  padding: 1rem 0;
}

.calculated-result {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background-color: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
}
</style>
