<template>
  <div class="inline-select-wrapper">
    <div v-if="showPlaceholder" class="inline-subclass-placeholder">-</div>
    <VirtualSelectField
      v-else
      :model-value="model"
      :options="currentOptions"
      :loading="isLoading"
      :disable="props.disable"
      :title="props.hint ? $t(props.hint) : undefined"
      hide-bottom-space
      dropdown-icon="expand_more"
      @update:model-value="onValueChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useEquipmentClassOptions } from '@/composables/useEquipmentClassOptions';
import VirtualSelectField from '@/components/molecules/VirtualSelectField.vue';
import type { Module, ConditionalSubmoduleProps } from '@/constant/modules';
import { MODULES, SUBMODULE_BUILDINGS_TYPES } from '@/constant/modules';
import { useModuleStore } from '@/stores/modules';
import { useBuildingRoomStore } from '@/stores/building_rooms';
import type { BuildingRoom } from '@/api/building_rooms';
import {
  buildingRoomOptions as mapBuildingRoomOptions,
  buildingRoomPatchPayload,
} from '@/utils/buildingRoomInline';
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

// Buildings room rows: the factor taxonomy's subkinds are room *types*, so
// the Local column must instead offer the ref-data rooms of the row's
// current building (#2501) — same source as the form dialog.
const isBuildingsRoom = computed(
  () =>
    props.moduleType === MODULES.Buildings &&
    props.submoduleType === SUBMODULE_BUILDINGS_TYPES.Building,
);
const buildingRoomStore = useBuildingRoomStore();
const buildingRooms = ref<BuildingRoom[]>([]);
const loadingRooms = ref(false);
let roomsRequestId = 0;

watch(
  () =>
    isBuildingsRoom.value && isSubClass.value && kindFieldId.value
      ? props.row[kindFieldId.value]
      : null,
  async (building) => {
    if (!building || typeof building !== 'string') {
      buildingRooms.value = [];
      return;
    }
    const requestId = ++roomsRequestId;
    loadingRooms.value = true;
    try {
      const rooms = await buildingRoomStore.fetchRooms(building);
      if (requestId !== roomsRequestId) return;
      buildingRooms.value = rooms;
    } catch {
      if (requestId === roomsRequestId) buildingRooms.value = [];
    } finally {
      if (requestId === roomsRequestId) loadingRooms.value = false;
    }
  },
  { immediate: true },
);

const buildingRoomOptions = computed(() =>
  mapBuildingRoomOptions(buildingRooms.value),
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

const currentOptions = computed(() => {
  if (isBuildingsRoom.value && isSubClass.value) {
    return buildingRoomOptions.value;
  }
  return isClass.value ? classOptions.value : subClassOptions.value;
});

const isLoading = computed(() => {
  if (isBuildingsRoom.value && isSubClass.value) return loadingRooms.value;
  return isClass.value ? loadingClasses.value : loadingSubclasses.value;
});

const showPlaceholder = computed(
  () =>
    isSubClass.value &&
    !isLoading.value &&
    currentOptions.value.length === 0 &&
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

  let payload: Record<string, string | number | boolean | null> = {
    [props.fieldId]: val,
  };
  // Picking a room also carries its ref-data room_type (the form dialog's
  // autofill) — without it the row would keep the old room's type (#2501).
  if (isBuildingsRoom.value && isSubClass.value) {
    payload = buildingRoomPatchPayload(val, buildingRooms.value);
  }

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
