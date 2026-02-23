<template>
  <div class="inline-select-wrapper">
    <div v-if="showPlaceholder" class="inline-subclass-placeholder"></div>
    <q-select
      v-else
      v-model="model"
      :options="options"
      emit-value
      map-options
      dense
      outlined
      hide-bottom-space
      class="inline-input"
      :loading="isLoading"
      :disable="props.disable"
      @update:model-value="onChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue';
import { QSelect } from 'quasar';
import {
  useClassificationTree,
  type TreeLevelConfig,
} from 'src/composables/useClassificationTree';
import { useFactorsStore } from 'src/stores/powerFactors';
import type { Module, ConditionalSubmoduleProps } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';

const moduleStore = useModuleStore();

interface ModuleRow {
  id: string | number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

type TableViewColumnSubset = {
  name: string;
  label: string;
  field: string;
  treeLevel?: number;
};

type CommonProps = {
  row: ModuleRow;
  fieldId: string;
  cols: TableViewColumnSubset[];
  unitId: number;
  year: string | number;
  disable?: boolean;
};

type ModuleTableProps = ConditionalSubmoduleProps & CommonProps;

const props = defineProps<ModuleTableProps>();

const treeLevels = computed<TreeLevelConfig[]>(() =>
  props.cols
    .filter((c) => c.treeLevel !== undefined)
    .sort((a, b) => a.treeLevel! - b.treeLevel!)
    .map((c) => ({ fieldId: c.field, optionKey: c.field })),
);

const factorsStore = useFactorsStore();

const { dynamicOptions, isPlaceholder, isLevelLoading } = useClassificationTree(
  props.row,
  toRef(props, 'submoduleType'),
  {
    levels: treeLevels.value,
    async onLeafChange(selections) {
      const cls = selections[0];
      if (!cls) return;
      const subCls = selections.length > 1 ? selections[1] : null;
      try {
        const pf = await factorsStore.fetchPowerFactor(
          props.submoduleType,
          cls,
          subCls,
        );
        if (pf) {
          if ('active_power_w' in props.row)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (props.row as any).active_power_w = pf.active_power_w;
          if ('standby_power_w' in props.row)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (props.row as any).standby_power_w = pf.standby_power_w;
        }
      } catch {
        // power factor lookup failed, user can still fill manually
      }
    },
  });

const classOptions = computed(() => {
  const taxo = moduleStore.state.taxonomySubmodule[props.submoduleType ?? ''];
  const opts = dynamicOptions['kind'] ?? [];
  return opts.map((opt) => {
    // Find node that includes the kind option
    const kindNode = taxo?.children?.find((node) => node.name === opt.value);
    return {
      value: opt.value,
      label: kindNode ? kindNode.label : opt.label || opt.value,
    };
  });
});
const subClassOptions = computed(() => {
  const taxo = moduleStore.state.taxonomySubmodule[props.submoduleType ?? ''];
  const opts = dynamicOptions['subkind'] ?? [];
  return opts.map((opt) => {
    // Find node that includes the subkind option
    const kindNode = taxo?.children?.find((node) =>
      node.children?.some((child) => child.name === opt.value),
    );
    // Then find the subkind node to get the label
    const subKindNode = kindNode?.children?.find(
      (child) => child.name === opt.value,
    );
    return {
      value: opt.value,
      label: subKindNode ? subKindNode.label : opt.label || opt.value,
    };
  });
});

const options = computed(() => dynamicOptions[props.fieldId] ?? []);

const isLoading = computed(() => isLevelLoading(props.fieldId));

const showPlaceholder = computed(() => isPlaceholder(props.fieldId));

const model = computed({
  get() {
    return props.row[props.fieldId] ?? '';
  },
  set(val: unknown) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (props.row as any)[props.fieldId] = val;
  },
});

async function onChange() {
  // Persist only the changed class/sub_class field.
  // Backend will auto-resolve power_factor_id and power values.
  const idNum = Number(props.row.id);
  if (!Number.isFinite(idNum)) return;

  const payload: Record<string, string | number | boolean | null> = {
    [props.fieldId]: model.value as string | number | boolean | null,
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
@use 'src/css/02-tokens' as tokens;

.inline-select-wrapper {
  width: 100%;
}

.inline-subclass-placeholder {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  border-radius: tokens.$field-border-radius;
  border: 1px solid rgba(0, 0, 0, 0.18);
  transition: border-color 0.36s cubic-bezier(0.4, 0, 0.2, 1);
  height: 2.5rem;
  background: linear-gradient(
    to bottom right,
    transparent 0%,
    transparent 49.5%,
    #e0e0e0 50.5%,
    #e0e0e0 100%
  );
  cursor: not-allowed;
}

.inline-input {
  width: 140px;
}
</style>
