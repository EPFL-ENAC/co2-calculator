<template>
  <div class="student-fte-calculator q-mx-md">
    <q-input
      ref="studentsRef"
      v-model.number="students"
      type="number"
      :label="$t('student_helper_students_label')"
      :min="0"
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
        :disable="!isValid"
        @click="handleUseValue"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { QInput } from 'quasar';

const { t: $t } = useI18n();

const students = ref<number | null>(null);
const duration = ref<number | null>(null);
const avgFTE = ref<number | null>(null);

const studentsRef = ref<QInput | null>(null);
const durationRef = ref<QInput | null>(null);
const avgFTERef = ref<QInput | null>(null);

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

const isValid = computed(() => {
  return (
    students.value !== null &&
    duration.value !== null &&
    avgFTE.value !== null &&
    students.value > 0 &&
    duration.value > 0 &&
    avgFTE.value > 0
  );
});

function handleUseValue() {
  emit('use-value', Number(calculatedFTE.value.toFixed(1)));
  // Clear inputs after using the value
  students.value = null;
  duration.value = null;
  avgFTE.value = null;
  // Reset validation state so button becomes disabled
  studentsRef.value?.resetValidation();
  durationRef.value?.resetValidation();
  avgFTERef.value?.resetValidation();
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
