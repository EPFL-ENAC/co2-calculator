<script setup lang="ts">
import { computed } from 'vue';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';

interface Props {
  title?: string;
  validatedUnits: number;
  totalUnits: number;
  scopeLabel?: string;
  helperText?: string;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Calculator Completion Rate',
  scopeLabel: 'in current selection',
  helperText: 'Each unit has equal weight, independent of FTE size',
  loading: false,
});

const percentage = computed(() => {
  if (props.totalUnits <= 0) {
    return 0;
  }
  return Math.round((props.validatedUnits / props.totalUnits) * 100);
});

const safeProgress = computed(
  () => Math.max(0, Math.min(percentage.value, 100)) / 100,
);
</script>

<template>
  <q-card flat bordered class="completion-rate-bar">
    <q-card-section class="q-pa-lg">
      <div class="row items-center justify-between q-mb-md">
        <div class="text-h6 text-weight-medium">{{ title }}</div>
        <q-icon
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer text-primary"
          :aria-label="$t('module-info-label')"
        >
          <q-tooltip class="u-tooltip">
            {{ helperText }}
          </q-tooltip>
        </q-icon>
      </div>

      <div class="row items-center justify-between q-mb-sm text-body1">
        <div>
          <strong>{{ validatedUnits }} validated units</strong>
          out of {{ totalUnits }} total units {{ scopeLabel }}
        </div>
        <div class="text-weight-bold">{{ percentage }}%</div>
      </div>

      <q-linear-progress
        :value="safeProgress"
        color="negative"
        track-color="grey-4"
        rounded
        size="8px"
      />

      <div class="text-body2 text-grey-7 q-mt-sm">
        {{ helperText }}
      </div>
    </q-card-section>
  </q-card>
</template>
