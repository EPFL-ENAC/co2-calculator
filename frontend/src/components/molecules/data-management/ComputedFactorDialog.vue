<script setup lang="ts">
import { matCalculate } from '@quasar/extras/material-icons';
import { outlinedClose } from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';

interface Props {
  modelValue: boolean;
}

defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
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
    <q-card style="min-width: 420px">
      <q-card-section class="row items-center q-pb-none">
        <q-icon :name="matCalculate" color="accent" size="sm" class="q-mr-sm" />
        <div class="text-h6">
          {{ $t('data_management_compute_factors_confirm_title') }}
        </div>
        <q-space />
        <q-btn
          flat
          size="md"
          :icon="outlinedClose"
          color="grey-6"
          @click="handleClose"
        />
      </q-card-section>
      <q-separator />
      <q-card-section class="text-body2">
        {{ $t('data_management_compute_factors_confirm_message') }}
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
