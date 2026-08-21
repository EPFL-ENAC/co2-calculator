<template>
  <div>
    <div class="text-weight-medium q-mb-sm">
      {{ $t('planner_budget_section_title') }}
    </div>
    <q-input
      v-model.number="input"
      class="planner-submodule-budget__input"
      type="number"
      outlined
      dense
      hide-bottom-space
      min="0"
      :suffix="currencyLabel(currency)"
      :label="$t('planner_submodule_budget_label', { submodule: name })"
      :loading="saving"
      :disable="disable"
      @blur="save"
      @keyup.enter="save"
    />
    <div class="text-body2 text-grey-7 q-mt-sm">
      {{ $t('planner_submodule_budget_hint') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { currencyLabel } from 'src/constant/currencies';
import { useSimulatorPlansStore } from 'src/stores/simulatorPlans';

const props = withDefaults(
  defineProps<{
    carbonReportId: number;
    moduleTypeId: number;
    submodule: string;
    name: string;
    currency: string | null | undefined;
    saved: number | null | undefined;
    disable?: boolean;
  }>(),
  { disable: false },
);

const emit = defineEmits<{ saving: [value: boolean] }>();

const { t } = useI18n();
const plansStore = useSimulatorPlansStore();

const input = ref<number | null>(props.saved ?? null);
const saving = ref(false);

async function save() {
  if (saving.value) return;
  const raw = input.value;
  const value =
    typeof raw === 'number' && Number.isFinite(raw) && raw >= 0 ? raw : null;
  if (value === (props.saved ?? null)) return;
  saving.value = true;
  emit('saving', true);
  try {
    await plansStore.setSubmoduleBudget(
      props.carbonReportId,
      props.moduleTypeId,
      props.submodule,
      value,
    );
  } catch {
    Notify.create({
      type: 'negative',
      message: t('planner_grant_budget_error'),
    });
  } finally {
    saving.value = false;
    emit('saving', false);
  }
}
</script>

<style scoped lang="scss">
.planner-submodule-budget__input {
  max-width: 240px;
}
</style>
