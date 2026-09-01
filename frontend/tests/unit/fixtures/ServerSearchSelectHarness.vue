<script setup lang="ts">
import { ref } from 'vue';
import ServerSearchSelectField from '@/components/molecules/ServerSearchSelectField.vue';
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
</script>

<template>
  <ServerSearchSelectField
    v-model="model"
    :module-type="props.moduleType"
    :submodule-type="props.submoduleType"
    :year="props.year"
    :initial-option="props.initialOption ?? null"
    label="code"
  />
  <div data-testid="selected">{{ model ?? '' }}</div>
</template>
