<template>
  <div class="inline-select-wrapper">
    <div
      v-if="showPlaceholder"
      class="inline-subclass-placeholder"
    ></div>
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

interface ModuleRow {
  id: string | number;
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
  cols: TableViewColumnSubset[];
  unitId: number;
  year: string | number;
  disable?: boolean;
};

type ModuleTableProps = ConditionalSubmoduleProps & CommonProps;

const props = defineProps<ModuleTableProps>();
const TREE_OPTION_IDS = ['kind', 'subkind', 'subsubkind'];

const treeLevels = computed<TreeLevelConfig[]>(() => {
  const levels: TreeLevelConfig[] = [];
  for (const optId of TREE_OPTION_IDS) {
    const col = props.cols.find((c) => c.optionsId === optId);
    if (col) levels.push({ fieldId: col.field, optionKey: optId });
  }
  return levels;
});

const factorsStore = useFactorsStore();

const { dynamicOptions, loading, isPlaceholder, isLevelLoading } =
  useClassificationTree(props.row, toRef(props, 'submoduleType'), {
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

const options = computed(
  () => dynamicOptions[props.optionsId] ?? [],
);

const isLoading = computed(() => isLevelLoading(props.optionsId));

const showPlaceholder = computed(() => isPlaceholder(props.optionsId));

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
  const { useModuleStore } = await import('src/stores/modules');
  const store = useModuleStore();
  const idNum = Number(props.row.id);
  if (!Number.isFinite(idNum)) return;

  const payload: Record<string, string | number | boolean | null> = {
    [props.fieldId]: model.value as string | number | boolean | null,
  };

  await store.patchItem(
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
