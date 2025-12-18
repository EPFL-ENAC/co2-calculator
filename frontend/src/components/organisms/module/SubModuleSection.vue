<template>
  <q-expansion-item
    v-if="submodule.tableNameKey"
    v-model="moduleStore.state.expandedSubmodules[submodule.id]"
    flat
    header-class="text-h5 text-weight-medium"
    class="q-mb-md container container--pa-none module-submodule-section q-mb-xl"
  >
    <template #header>
      <div class="row flex items-center full-width">
        <div class="col">
          {{
            $t(submodule.tableNameKey, {
              count: submoduleCount || 0,
            })
          }}
        </div>
        <q-icon
          v-if="hasTableTooltip"
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer q-mr-sm"
          :aria-label="
            $t(`${moduleType}-${submoduleType}-table-title-info-label`)
          "
        >
          <q-tooltip
            v-if="hasTableTooltip"
            anchor="center right"
            self="top right"
            class="u-tooltip"
          >
            {{ $t(`${moduleType}-${submoduleType}-table-title-info-tooltip`) }}
          </q-tooltip>
        </q-icon>
      </div>
    </template>
    <q-separator />
    <q-card-section class="q-pa-none">
      <div v-if="submodule.moduleFields" class="q-mx-lg q-my-xl">
        <module-table
          :module-fields="submodule.moduleFields"
          :unit-id="unitId"
          :year="year"
          :threshold="threshold"
          :has-top-bar="submodule.hasTableTopBar"
          :module-type="moduleType"
          :submodule-type="submodule.type"
          :moduleconfig="submodule"
        />
      </div>
      <q-separator />
      <div v-if="submodule.moduleFields">
        <module-form
          :fields="submodule.moduleFields"
          :submodule-type="submodule.type"
          :module-type="moduleType"
          :item="item"
          :has-subtitle="submodule.hasFormSubtitle"
          :has-student-helper="submodule.hasStudentHelper"
          :has-add-with-note="submodule.hasFormAddWithNote"
          :add-button-label-key="submodule.addButtonLabelKey"
          @submit="submitForm"
        />
      </div>
    </q-card-section>
  </q-expansion-item>
</template>

<script setup lang="ts">
import { Submodule as ConfigSubmodule } from 'src/constant/moduleConfig';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import type {
  ModuleResponse,
  Threshold,
  ConditionalSubmoduleProps,
} from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
const moduleStore = useModuleStore();

type CommonProps = {
  submodule: ConfigSubmodule;
  loading?: boolean;
  error?: string | null;
  data?: ModuleResponse | null;
  unitId: string;
  year: string | number;
  threshold: Threshold;
};

type SubModuleSectionProps = ConditionalSubmoduleProps & CommonProps;

const props = defineProps<SubModuleSectionProps>();

const submoduleCount = computed(
  () =>
    moduleStore.state.data?.submodules?.[props.submodule.type]?.summary
      ?.total_items || 0,
);

const item = computed(() => {
  if (props.moduleType === 'my-lab' && props.submoduleType === 'student') {
    return moduleStore.state.dataSubmodule?.[props.submodule.type]?.items[0];
  }
  return null;
});
const { te } = useI18n();

const hasTableTooltip = computed(() => {
  if (!props.submodule.type) return false;
  const tooltipKey = `${props.moduleType}-${props.submodule.type}-table-title-info-tooltip`;
  return te(tooltipKey);
});

// actions

function submitForm(payload: Record<string, FieldValue>) {
  // if update! (for my-lab student for instance)
  if (item.value && item.value.id) {
    return moduleStore.patchItem(
      props.moduleType,
      props.submoduleType,
      String(props.unitId),
      String(props.year),
      item.value.id,
      payload,
    );
  } else {
    moduleStore.postItem(
      props.moduleType,
      props.unitId,
      props.year,
      props.submoduleType,
      payload,
    );
  }
}
</script>
