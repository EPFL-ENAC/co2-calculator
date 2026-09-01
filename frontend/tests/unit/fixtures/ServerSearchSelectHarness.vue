<script setup lang="ts">
import { ref } from 'vue';
import VirtualSelectField from '@/components/molecules/VirtualSelectField.vue';
import { searchDataEntryOptions } from '@/api/taxonomies';
import { i18n, type MessageLanguages } from '@/boot/i18n';

const props = defineProps<{
  moduleType: string;
  submoduleType: string;
  year?: number;
  initialOption?: { value: string; label: string } | null;
  initialValue?: string | null;
  locale?: MessageLanguages;
}>();

if (props.locale) {
  i18n.global.locale.value = props.locale;
}

const model = ref<string | number | null>(props.initialValue ?? null);

// Mirrors ModuleForm's `searchClassificationOptions` callback, year guard
// included — the specs pin the request shape end to end through it.
async function onSearch(query: string) {
  if (props.year == null) return [];
  const found = await searchDataEntryOptions(
    props.moduleType,
    props.submoduleType,
    query,
    props.year,
  );
  return found.map((o) => ({ value: o.name, label: o.label }));
}
</script>

<template>
  <VirtualSelectField
    v-model="model"
    :on-search="onSearch"
    :initial-option="props.initialOption ?? null"
    label="code"
  />
  <div data-testid="selected">{{ model ?? '' }}</div>
</template>
