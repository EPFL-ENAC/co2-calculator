<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useModuleStore } from '@/stores/modules';
import { i18n, type MessageLanguages } from '@/boot/i18n';
import { MODULES } from '@/constant/modules';

const props = defineProps<{
  locale: MessageLanguages;
}>();

watch(
  () => props.locale,
  (value) => {
    i18n.global.locale.value = value;
  },
  { immediate: true },
);

const moduleStore = useModuleStore();

onMounted(async () => {
  moduleStore.initializeSubmoduleState('other_purchases');
  await moduleStore.getSubmoduleData({
    moduleType: MODULES.Purchase,
    submoduleType: 'other_purchases',
    unit: 7,
    year: '2024',
    carbonReportId: 42,
  });
});
</script>

<template>
  <div data-testid="loaded">
    {{ moduleStore.state.loadedSubmodules['other_purchases'] ? 'yes' : 'no' }}
  </div>
</template>
