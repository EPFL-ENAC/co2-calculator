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

function fetchRows() {
  moduleStore.getSubmoduleData({
    moduleType: MODULES.Purchase,
    submoduleType: 'other_purchases',
    unit: 7,
    year: '2024',
    carbonReportId: 42,
  });
}

// Mirrors ModuleTable's wiring: the component owning the fetch watches
// the locale and re-runs its own fetch with its current args.
watch(() => i18n.global.locale.value, fetchRows);

onMounted(() => {
  moduleStore.initializeSubmoduleState('other_purchases');
  fetchRows();
});
</script>

<template>
  <div data-testid="loaded">
    {{ moduleStore.state.loadedSubmodules['other_purchases'] ? 'yes' : 'no' }}
  </div>
</template>
