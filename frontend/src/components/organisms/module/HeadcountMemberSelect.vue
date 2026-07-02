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
    :disable="!loading && members.length === 0 && !canEditHeadcount"
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
import {
  TRAVELER_OTHER_INTERNAL,
  TRAVELER_OTHER_EXTERNAL,
  TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
} from 'src/constant/module-config/traveler-options';
import { useAuthStore } from 'src/stores/auth';
import { useModuleStore } from 'src/stores/modules';
import {
  getHeadcountMembers,
  type HeadcountMemberDropdownItem,
} from 'src/api/modules';
import { PermissionAction } from 'src/stores/auth';

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
const moduleStore = useModuleStore();
const canEditHeadcount = computed(() =>
  authStore.hasUserModulePermission(MODULES.Headcount, PermissionAction.EDIT),
);
const isNotValidated = computed(
  () => members.value.length === 0 && !canEditHeadcount.value,
);

function buildOptions(list: HeadcountMemberDropdownItem[]): SelectOption[] {
  return list.map((m) => ({
    label: `${m.name}`,
    value: m.institutional_id,
  }));
}

const memberOptions = ref<SelectOption[]>([]);

// Two static "Other traveler" sentinels are always offered after the real
// headcount members (issue #1153), so a manager can attribute a trip to a
// traveler who isn't in this unit's headcount. Built as a computed so the
// labels re-translate on locale change.
const options = computed<SelectOption[]>(() => [
  ...memberOptions.value,
  {
    label: $t(TRAVELER_OTHER_INTERNAL_LABEL_KEY),
    value: TRAVELER_OTHER_INTERNAL,
  },
  {
    label: $t(TRAVELER_OTHER_EXTERNAL_LABEL_KEY),
    value: TRAVELER_OTHER_EXTERNAL,
  },
]);

async function fetchMembers() {
  if (!props.unitId || !props.year) return;
  loading.value = true;
  try {
    members.value = await getHeadcountMembers(
      props.unitId,
      props.year,
      moduleStore.carbonProjectType,
    );
    memberOptions.value = buildOptions(members.value);
    // Standard users (no Headcount edit) are auto-attributed to their own
    // headcount entry. Only auto-emit a REAL member — never a sentinel — so a
    // standard user without a headcount entry is not silently misattributed.
    if (!canEditHeadcount.value && memberOptions.value.length > 0) {
      emit('update:modelValue', memberOptions.value[0].value);
    }
  } catch {
    members.value = [];
    memberOptions.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(fetchMembers);
</script>
