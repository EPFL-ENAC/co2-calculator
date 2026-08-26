<template>
  <div class="inline-select-wrapper">
    <div v-if="showPlaceholder" class="inline-subclass-placeholder">-</div>
    <VirtualSelectField
      v-else
      :model-value="model"
      :options="currentOptions"
      :loading="isClass ? loadingClasses : loadingSubclasses"
      :disable="props.disable"
      :title="props.hint ? $t(props.hint) : undefined"
      hide-bottom-space
      dropdown-icon="expand_more"
      @update:model-value="onValueChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useEquipmentClassOptions } from '@/composables/useEquipmentClassOptions';
import VirtualSelectField from '@/components/molecules/VirtualSelectField.vue';
import type { Module, ConditionalSubmoduleProps } from '@/constant/modules';
import { useModuleStore } from '@/stores/modules';
import { sortByOrder } from '@/utils/options';
import { resolveFactorYear } from '@/utils/factor-year';

const moduleStore = useModuleStore();

interface ModuleRow {
  id: string | number;
  // allow arbitrary additional fields
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

type TableViewColumnSubset = {
  name: string;
  label: string;
  field: string;
  optionsId?: string;
};

type CommonProps = {
  row: ModuleRow;
  fieldId: string;
  optionsId: string;
  optionLabelKey?: string;
  optionLabelPrefix?: string;
  optionOrder?: string[];
  hint?: string;
  cols: TableViewColumnSubset[];
  unitId: number;
  year: string | number;
  /**
   * Year whose factors the class/subclass options come from. See ModuleForm —
   * the Simulator Plan passes its reference year, `null` when unset. `year`
   * stays the row's own year: it addresses the entry for the PATCH.
   */
  factorYear?: number | null;
  disable?: boolean;
};

type ModuleTableProps = ConditionalSubmoduleProps & CommonProps;

const props = defineProps<ModuleTableProps>();
const { t, te } = useI18n();
const factorYear = computed(() =>
  resolveFactorYear(props.factorYear, props.year),
);
const isClass = computed(() => props.optionsId === 'kind');
const isSubClass = computed(() => props.optionsId === 'subkind');

const kindFieldId = computed(() => {
  const kindField = props.cols.find((f) => f.optionsId === 'kind');
  return kindField ? kindField.field : null;
});

const subkindFieldId = computed(() => {
  const subkindField = props.cols.find((f) => f.optionsId === 'subkind');
  return subkindField ? subkindField.field : null;
});

const { dynamicOptions, loadingClasses, loadingSubclasses } =
  useEquipmentClassOptions(
    props.row,
    toRef(props, 'moduleType'),
    toRef(props, 'submoduleType'),
    {
      classFieldId: kindFieldId.value,
      subClassFieldId: subkindFieldId.value,
    },
    factorYear,
  );

const classOptions = computed(() => {
  const taxo = moduleStore.state.taxonomySubmodule[props.submoduleType ?? ''];
  const opts = dynamicOptions['kind'] ?? [];
  // Build O(1) lookup map to avoid O(n²) Array.find() over 10k taxonomy children
  const kindNodeMap = new Map(taxo?.children?.map((c) => [c.name, c]) ?? []);
  const mapped = opts.map((opt) => {
    if (props.optionLabelKey) {
      const key = props.optionLabelKey.replace(
        '{value}',
        opt.value.toLowerCase(),
      );
      return {
        value: opt.value,
        label: te(key) ? t(key) : opt.value,
      };
    }
    const kindNode = kindNodeMap.get(opt.value);
    const translationKey = kindNode?.translation_key;
    if (translationKey && te(translationKey)) {
      return { value: opt.value, label: t(translationKey) };
    }
    if (te(opt.value)) {
      return { value: opt.value, label: t(opt.value) };
    }
    return {
      value: opt.value,
      label: kindNode ? kindNode.label : opt.label || opt.value,
    };
  });
  return props.optionOrder ? sortByOrder(mapped, props.optionOrder) : mapped;
});
const subClassOptions = computed(() => {
  const taxo = moduleStore.state.taxonomySubmodule[props.submoduleType ?? ''];
  const opts = dynamicOptions['subkind'] ?? [];
  // Build flat map of subkind name → node to avoid nested O(n²) finds
  const subKindNodeMap = new Map<string, { label: string; name: string }>();
  taxo?.children?.forEach((kindNode) => {
    kindNode.children?.forEach((child) => {
      subKindNodeMap.set(child.name, child);
    });
  });
  return opts.map((opt) => {
    if (props.optionLabelPrefix) {
      return {
        value: opt.value,
        label: t(opt.value.toLowerCase(), opt.label || opt.value),
      };
    }
    const subKindNode = subKindNodeMap.get(opt.value);
    return {
      value: opt.value,
      label: subKindNode ? subKindNode.label : opt.label || opt.value,
    };
  });
});

const currentOptions = computed(() =>
  isClass.value ? classOptions.value : subClassOptions.value,
);

const showPlaceholder = computed(
  () =>
    isSubClass.value &&
    !loadingSubclasses.value &&
    subClassOptions.value.length === 0 &&
    !model.value,
);

const model = computed({
  get() {
    return props.row[props.fieldId] ?? '';
  },
  set(val: unknown) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (props.row as any)[props.fieldId] = val;
  },
});

async function onValueChange(val: string | number | null) {
  model.value = val;

  const idNum = Number(props.row.id);
  if (!Number.isFinite(idNum)) return;

  const payload: Record<string, string | number | boolean | null> = {
    [props.fieldId]: val,
  };

  await moduleStore.patchItem(
    props.moduleType as Module,
    props.submoduleType,
    props.unitId,
    String(props.year),
    idNum,
    payload,
  );
}
</script>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

.inline-select-wrapper {
  width: 100%;
}

.inline-subclass-placeholder {
  width: 100%;
  display: flex;
  align-items: center;
  height: 2.5rem;
  padding-left: tokens.$spacing-sm;
  color: tokens.$table-color-disabled;
  cursor: default;
}
</style>
