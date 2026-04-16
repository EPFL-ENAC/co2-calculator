<template>
  <q-input
    v-if="!canEditHeadcount && members.length > 0"
    :model-value="options[0].label"
    readonly
    dense
    outlined
    :label="label"
    :error="error"
    :error-message="errorMessage"
  />
  <q-select
    v-else
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
        ? $t(
            isNotValidated
              ? `${MODULES.ProfessionalTravel}-field-traveler-not-validated`
              : `${MODULES.ProfessionalTravel}-field-traveler-empty-headcount`,
          )
        : undefined
    "
    :disable="!loading && members.length === 0"
    dense
    outlined
    clearable
    @update:model-value="$emit('update:modelValue', $event as string | null)"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES } from 'src/constant/modules';
import { useAuthStore } from 'src/stores/auth';
import { hasPermission } from 'src/utils/permission';
import {
  getHeadcountMembers,
  type HeadcountMemberDropdownItem,
} from 'src/api/modules';

const { t: $t } = useI18n();

const props = defineProps<{
  modelValue: string | null;
  unitId?: number;
  year?: number | string;
  label?: string;
  error?: boolean;
  errorMessage?: string;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void;
}>();

interface SelectOption {
  label: string;
  value: string;
}

const loading = ref(false);
const members = ref<HeadcountMemberDropdownItem[]>([]);
const authStore = useAuthStore();
const canEditHeadcount = computed(() =>
  hasPermission(authStore.user?.permissions, 'modules.headcount', 'edit'),
);
const isNotValidated = computed(
  () => members.value.length === 0 && !canEditHeadcount.value,
);
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
    if (!canEditHeadcount.value && options.value.length > 0) {
      emit('update:modelValue', options.value[0].value);
    }
  } catch {
    members.value = [];
    options.value = [];
  } finally {
    loading.value = false;
  }
});
</script>
