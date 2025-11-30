<template>
  <q-card class="q-mb-md">
    <q-card-section>
      <div class="row items-center justify-between">
        <div>
          <h3 class="q-mb-xs">{{ submodule.name }}</h3>
          <div v-if="submodule.count !== undefined" class="text-subtle">
            Count: {{ submodule.count }}
          </div>
        </div>
      </div>

      <div v-if="submodule.tableColumns" class="q-mt-md">
        <module-table
          :columns="submodule.tableColumns"
          :rows="rows"
          :loading="loading"
          :error="error"
        />
      </div>

      <div v-if="submodule.formInputs" class="q-mt-md">
        <module-form :inputs="submodule.formInputs" />
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { Submodule as ConfigSubmodule } from 'src/constant/moduleConfig';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';
import { computed } from 'vue';

export interface ModuleItem {
  name: string;
  class?: string;
  sub_class?: string;
  act_usage?: number;
  pas_usage?: number;
  act_power?: number;
  pas_power?: number;
  kg_co2eq?: number;
  // add id later if you generate one client-side
  id?: string;
}

export interface Submodule {
  id: string;
  name: string;
  count?: number;
  items: ModuleItem[];
  summary: {
    total_items: number;
    annual_consumption_kwh: number;
    total_kg_co2eq: number;
  };
}

export interface Totals {
  total_submodules: number;
  total_items: number;
  total_annual_consumption_kwh: number;
  total_kg_co2eq: number;
}

export interface ModuleResponse {
  module_type: string;
  unit: string;
  year: string;
  retrieved_at: string;
  // map keyed by submodule id (per your backend change)
  submodules: Record<string, Submodule>;
  totals: Totals;
}

const props = defineProps<{
  submodule: ConfigSubmodule;
  loading?: boolean;
  error?: string | null;
  data?: ModuleResponse | null;
}>();

const rows = computed(() => {
  const items = props.data?.submodules?.[props.submodule.id]?.items ?? [];
  // ensure stable id for q-table row-key
  return (items as ModuleItem[]).map((it, i) => ({
    id: it.id ?? `${props.submodule.id}_${i}`,
    ...it,
  }));
});
</script>
