<script setup lang="ts">
import { matCalendarMonth } from '@quasar/extras/material-icons';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useYearConfigStore } from '@/stores/yearConfig';

const props = defineProps<{ year: number }>();

const yearConfigStore = useYearConfigStore();
const { t: $t } = useI18n();

// U5 — flip is_started=true for the selected year.
const handleOpenForUsers = async () => {
  try {
    await yearConfigStore.openForUsers(props.year);
    Notify.create({
      type: 'positive',
      message: $t('data_management_year_opened_success', { year: props.year }),
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    Notify.create({ type: 'negative', message: msg });
  }
};
</script>

<template>
  <q-btn
    :icon="matCalendarMonth"
    color="accent"
    :label="$t('open_year_for_users')"
    class="text-weight-medium text-capitalize q-mt-md"
    :loading="yearConfigStore.loading"
    :disable="
      yearConfigStore.anyModuleIncomplete ||
      !!yearConfigStore.config?.is_started
    "
    data-testid="open-year-for-users-btn"
    @click="handleOpenForUsers"
  >
    <q-tooltip v-if="yearConfigStore.config?.is_started">
      {{ $t('backoffice-data-management-year-already-open') }}
    </q-tooltip>
    <q-tooltip v-else-if="yearConfigStore.anyModuleIncomplete">
      {{ $t('backoffice-data-management-open-year-disabled') }}
    </q-tooltip>
  </q-btn>
</template>
