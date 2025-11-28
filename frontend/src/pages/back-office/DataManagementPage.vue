<script setup lang="ts">
import { ref } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import { MODULES_LIST } from 'src/constant/modules';
import NavigationHeader from 'src/components/organisms/NavigationHeader.vue';
import { type ModuleThreshold } from 'src/constant/modules';
import ModuleConfig from 'src/components/organisms/data-management/ModuleConfig.vue';

const moduleThresholds = ref(
  MODULES_LIST.reduce(
    (acc, module) => {
      acc[module] = {
        module,
        threshold: { type: 'fixed', value: 0 },
      };
      return acc;
    },
    {} as { [key: string]: ModuleThreshold },
  ),
);
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />

    <div class="q-my-xl q-px-xl">
      <template v-for="(module, idx) in MODULES_LIST" :key="idx">
        <module-config v-model="moduleThresholds[module]" class="q-mb-lg" />
      </template>
    </div>
  </q-page>
</template>
