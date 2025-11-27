<script setup lang="ts">
import { ref } from 'vue';
import { MODULES_LIST } from 'src/constant/modules';
import { type ModuleThreshold } from 'src/constant/modules';
import ModuleConfig from 'src/components/organisms/data-management/ModuleConfig.vue';

interface Props {
  year: number;
}
defineProps<Props>();

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
  <div>
    <template v-for="module in MODULES_LIST" :key="module">
      <module-config
        v-model="moduleThresholds[module]"
        :year="year"
        class="q-mb-lg"
      />
    </template>
  </div>
</template>
