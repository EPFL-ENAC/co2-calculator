<template>
  <q-select
    :model-value="modelValue"
    :label="label"
    :options="options"
    option-label="label"
    option-value="value"
    emit-value
    map-options
    :loading="loading"
    :error="error"
    :error-message="errorMessage"
    :hint="
      !loading && members.length === 0
        ? $t(`${MODULES.ProfessionalTravel}-field-traveler-empty-headcount`)
        : undefined
    "
    :disable="!loading && members.length === 0"
    dense
    outlined
    clearable
    @update:model-value="$emit('update:modelValue', $event as number | null)"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES } from 'src/constant/modules';
import {
  getHeadcountMembers,
  type HeadcountMemberDropdownItem,
} from 'src/api/modules';

const { t: $t } = useI18n();

const props = defineProps<{
  modelValue: number | null;
  unitId?: number;
  year?: number | string;
  label?: string;
  error?: boolean;
  errorMessage?: string;
}>();

defineEmits<{
  (e: 'update:modelValue', value: number | null): void;
}>();

interface SelectOption {
  label: string;
  value: number;
}

const loading = ref(false);
const members = ref<HeadcountMemberDropdownItem[]>([]);
const options = ref<SelectOption[]>([]);

function buildOptions(list: HeadcountMemberDropdownItem[]): SelectOption[] {
  return list.map((m) => ({
    label: `${m.name}`,
    value: m.institutional_id,
  }));
}

onMounted(async () => {
  if (!props.unitId || !props.year) return;
  loading.value = true;
  try {
    members.value = await getHeadcountMembers(props.unitId, props.year);
    options.value = buildOptions(members.value);
  } catch {
    members.value = [];
    options.value = [];
  } finally {
    loading.value = false;
  }
});
</script>
