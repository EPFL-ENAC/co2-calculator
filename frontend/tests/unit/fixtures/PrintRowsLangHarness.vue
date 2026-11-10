<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { i18n, type MessageLanguages } from '@/boot/i18n';
import type { Module } from '@/constant/modules';
import { fetchAllSubmoduleRows } from '@/utils/printSubmoduleRows';

const props = defineProps<{
  moduleType: Module;
  submoduleId: string;
  carbonReportId: number;
  locale: MessageLanguages;
}>();

const rowCount = ref<number | null>(null);

onMounted(async () => {
  i18n.global.locale.value = props.locale;
  const rows = await fetchAllSubmoduleRows(
    props.moduleType,
    props.submoduleId,
    props.carbonReportId,
  );
  rowCount.value = rows.length;
});
</script>

<template>
  <div data-testid="rows">{{ rowCount ?? 'loading' }}</div>
</template>
