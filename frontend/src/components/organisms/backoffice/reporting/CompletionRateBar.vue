<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';

interface Props {
  title?: string;
  validatedUnits: number;
  totalUnits: number;
  scopeLabel?: string;
  helperText?: string;
}

const { t } = useI18n();

const props = withDefaults(defineProps<Props>(), {
  title: undefined,
  scopeLabel: undefined,
  helperText: undefined,
});

const resolvedTitle = computed(
  () => props.title ?? t('backoffice_reporting_completion_bar_title'),
);
const resolvedHelperText = computed(
  () => props.helperText ?? t('backoffice_reporting_completion_bar_helper'),
);
const resolvedScopeLabel = computed(
  () => props.scopeLabel ?? t('backoffice_reporting_completion_bar_scope'),
);

const percentage = computed(() => {
  if (props.totalUnits <= 0) {
    return 0;
  }
  return Math.round((props.validatedUnits / props.totalUnits) * 100);
});

const safeProgress = computed(
  () => Math.max(0, Math.min(percentage.value, 100)) / 100,
);

const barColor = computed(() => {
  if (percentage.value >= 70) return 'positive';
  if (percentage.value >= 30) return 'warning';
  return 'negative';
});
</script>

<template>
  <q-card flat bordered class="completion-rate-bar">
    <q-card-section class="q-pa-lg">
      <div class="row items-center justify-between q-mb-md">
        <div class="text-h6 text-weight-medium">{{ resolvedTitle }}</div>
        <q-icon
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer text-primary"
          :aria-label="$t('module-info-label')"
        >
          <q-tooltip class="u-tooltip">
            {{ resolvedHelperText }}
          </q-tooltip>
        </q-icon>
      </div>

      <div class="row items-center justify-between q-mb-sm text-body1">
        <div>
          {{
            $t('backoffice_reporting_completion_bar_count', {
              validated: validatedUnits,
              total: totalUnits,
              scope: resolvedScopeLabel,
            })
          }}
        </div>
        <div class="text-weight-bold">{{ percentage }}%</div>
      </div>

      <q-linear-progress
        :value="safeProgress"
        :color="barColor"
        track-color="grey-4"
        rounded
        size="8px"
      />

      <div class="text-body2 text-grey-7 q-mt-sm">
        {{ resolvedHelperText }}
      </div>
    </q-card-section>
  </q-card>
</template>
