<template>
  <div>
    <q-form ref="formRef" class="student-fte-calculator q-mx-md">
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
    </q-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
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

// Use Quasar form validation instead of hardcoded checks
const isFormValid = ref(false);

// Watch form values and validate using Quasar's validation
watch(
  [students, duration, avgFTE],
  async () => {
    if (!formRef.value) {
      isFormValid.value = false;
      return;
    }
    const result = await formRef.value.validate();
    isFormValid.value = result;
  },
  { flush: 'post' },
);

let lastEmitted: number | null = null;

// Watch transition to valid + value change
watch(
  [isFormValid, calculatedFTE],
  ([valid, fte]) => {
    if (!valid) return;

    const rounded = Number(fte.toFixed(1));

    if (rounded !== lastEmitted) {
      lastEmitted = rounded;
      emit('use-value', rounded);
    }
  },
  { flush: 'post' },
);

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
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.student-fte-calculator {
  display: flex;
  flex-direction: column;
  gap: tokens.$spacing-md;
  padding: 1rem 0;
}
</style>
