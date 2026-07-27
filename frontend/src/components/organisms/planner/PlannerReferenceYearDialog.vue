<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <q-card style="min-width: 460px">
      <q-card-section class="row items-center q-pb-none">
        <q-icon
          name="o_calendar_month"
          size="sm"
          color="info"
          class="q-mr-sm"
        />
        <div class="text-h4 text-weight-medium">
          {{ $t('planner_reference_year_dialog_title', { year }) }}
        </div>
        <q-space />
        <q-btn v-close-popup flat size="md" icon="o_close" color="grey-6" />
      </q-card-section>

      <q-separator class="q-mt-sm" />

      <q-card-section>
        <q-select
          v-model="selected"
          :options="options"
          :label="$t('planner_reference_year_dialog_select_label')"
          outlined
          dense
          emit-value
          map-options
        />
        <div class="text-body2 text-grey-8 q-mt-md">
          {{ $t('planner_reference_year_dialog_consequences', { year }) }}
        </div>

        <template v-if="referenceYear !== null">
          <q-banner dense rounded class="bg-red-1 text-negative q-mt-md">
            <template #avatar>
              <q-icon name="o_warning" color="negative" size="sm" />
            </template>
            <div class="text-body2">
              {{ $t('planner_reference_year_dialog_wipe_warning', { year }) }}
            </div>
          </q-banner>
          <q-checkbox
            v-model="acknowledged"
            dense
            color="negative"
            class="q-mt-md"
            :label="$t('planner_reference_year_dialog_wipe_ack', { year })"
          />
        </template>
      </q-card-section>

      <q-card-actions class="q-px-md q-pb-md">
        <q-btn
          :label="$t('common_validate_short')"
          :disable="confirmDisabled"
          :loading="loading"
          color="info"
          unelevated
          no-caps
          class="text-weight-medium"
          @click="onConfirm"
        />
        <q-btn
          v-close-popup
          :label="$t('common_cancel')"
          color="primary"
          unelevated
          outline
          no-caps
          class="text-weight-medium"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const props = defineProps<{
  modelValue: boolean;
  /** The plan year this dialog sets the baseline for. */
  year: number;
  referenceYear: number | null;
  options: { label: string; value: number }[];
  loading: boolean;
}>();
const emit = defineEmits<{
  'update:modelValue': [open: boolean];
  confirm: [referenceYear: number];
}>();

// Seeded once per mount: the parent keys the dialog on the current reference
// year, so a re-open starts from what is set rather than the last pick.
const selected = ref<number | null>(props.referenceYear);

// Changing a baseline that is already set deletes the prefilled modules' data,
// so the user has to acknowledge it. The first-time set deletes nothing.
const acknowledged = ref(false);

const confirmDisabled = computed(
  () =>
    selected.value === null ||
    selected.value === props.referenceYear ||
    (props.referenceYear !== null && !acknowledged.value),
);

function onConfirm() {
  if (selected.value === null) return;
  emit('confirm', selected.value);
}
</script>
