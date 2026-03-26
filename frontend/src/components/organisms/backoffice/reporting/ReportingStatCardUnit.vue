<script setup lang="ts">
import { useI18n } from 'vue-i18n';
const { t } = useI18n();

interface Props {
  validatedModules: number;
  totalModules: number;
  loading?: boolean;
}

defineProps<Props>();
</script>

<template>
  <q-card flat bordered class="stat-card">
    <q-card-section class="justify-between w-full d-flex q-pa-none">
      <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
        {{ t('backoffice_reporting_usage_box_one_unit') }}
      </span>
    </q-card-section>
    <q-card-section
      class="text-h1 text-weight-bold q-pa-none"
      style="color: #007480"
    >
      <q-skeleton v-if="loading" type="text" width="80px" height="38px" />
      <template v-else> {{ validatedModules }}/{{ totalModules }} </template>
    </q-card-section>
  </q-card>
</template>

<style scoped lang="scss">
.stat-card {
  border-radius: 3px;
  padding: 24px;

  display: flex;
  flex-direction: column;
  justify-content: space-between;

  margin-top: 24px;
  gap: 12px;
}
</style>
