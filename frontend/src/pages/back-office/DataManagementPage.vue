<script setup lang="ts">
import { ref } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import AnnualDataImport from 'src/components/organisms/data-management/AnnualDataImport.vue';
import ModulesConfig from 'src/components/organisms/data-management/ModulesConfig.vue';

const availableYears = ref<number[]>([2022, 2023, 2024]);
const selectedYear = ref<number>(
  availableYears.value[availableYears.value.length - 1],
);
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />

    <div class="q-my-xl q-px-xl">
      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="text-h5">{{ $t('data_management_reporting_year') }}</div>
        <q-select
          v-model="selectedYear"
          :options="availableYears"
          outlined
          dense
          class="q-my-md"
        >
          <template #prepend>
            <q-icon name="event" color="accent" size="xs" />
          </template>
        </q-select>
        <div>
          {{ $t('data_management_reporting_year_hint') }}
        </div>
      </q-card>
      <annual-data-import :year="selectedYear" />
      <modules-config :year="selectedYear" />
    </div>
  </q-page>
</template>
