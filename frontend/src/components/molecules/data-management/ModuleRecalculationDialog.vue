<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { RecalculationStatusEntry } from 'src/stores/yearConfig';

interface Props {
  modelValue: boolean;
  moduleTypeId: number | null;
  staleTypes: RecalculationStatusEntry[];
  onlyStale: boolean;
}

defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'update:onlyStale', value: boolean): void;
  (e: 'confirm'): void;
  (e: 'cancel'): void;
}>();

const { t: $t } = useI18n();

function handleClose() {
  emit('cancel');
  emit('update:modelValue', false);
}

function handleConfirm() {
  emit('confirm');
  emit('update:modelValue', false);
}
</script>

<template>
  <q-dialog
    :model-value="modelValue"
    persistent
    @update:model-value="emit('update:modelValue', $event)"
  >
    <q-card style="min-width: 480px">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="refresh" color="accent" size="sm" class="q-mr-sm" />
        <div class="text-h6">
          {{ $t('data_management_recalculate_emissions_title') }}
        </div>
        <q-space />
        <q-btn
          flat
          size="md"
          icon="o_close"
          color="grey-6"
          @click="handleClose"
        />
      </q-card-section>
      <q-separator />
      <q-card-section class="text-body2">
        {{ $t('data_management_recalculate_emissions_description') }}
      </q-card-section>
      <q-card-section v-if="moduleTypeId !== null">
        <q-radio
          :model-value="onlyStale"
          val="true"
          :label="$t('data_management_recalculate_only_stale')"
          color="accent"
          @update:model-value="(val) => emit('update:onlyStale', val)"
        />
        <div class="text-caption text-grey-7 q-ml-md q-mt-xs">
          {{
            $t('data_management_stale_types', {
              count: staleTypes.length,
            })
          }}
        </div>
        <q-radio
          :model-value="onlyStale"
          val="false"
          :label="$t('data_management_recalculate_all')"
          color="accent"
          class="q-mt-sm"
          @update:model-value="(val) => emit('update:onlyStale', val)"
        />
      </q-card-section>
      <q-card-actions class="q-px-md q-pb-md">
        <q-btn flat :label="$t('common_cancel')" @click="handleClose" />
        <q-btn
          color="accent"
          unelevated
          :label="$t('common_confirm')"
          @click="handleConfirm"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped></style>
