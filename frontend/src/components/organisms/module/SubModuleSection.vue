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
        <module-table :columns="submodule.tableColumns" />
      </div>

      <div v-if="submodule.formInputs" class="q-mt-md">
        <module-form :inputs="submodule.formInputs" />
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { Submodule } from 'src/constant/moduleConfig';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';

defineProps<{ submodule: Submodule }>();
</script>
