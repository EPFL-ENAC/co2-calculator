<script setup lang="ts">
import { onMounted } from 'vue';
import { useModuleStore } from '@/stores/modules';
import { i18n, type MessageLanguages } from '@/boot/i18n';
import type { Module } from '@/constant/modules';

const props = defineProps<{
  moduleType: Module;
  submoduleType: string;
  year: string;
  locale: MessageLanguages;
}>();

const moduleStore = useModuleStore();

onMounted(async () => {
  i18n.global.locale.value = props.locale;
  await moduleStore.getSubmoduleTaxonomy(
    props.moduleType,
    props.submoduleType,
    props.year,
  );
});
</script>

<template>
  <div>harness-ready</div>
  <div data-testid="taxonomy">
    {{
      moduleStore.state.taxonomySubmodule[props.submoduleType]
        ? 'resolved'
        : 'missing'
    }}
  </div>
</template>
