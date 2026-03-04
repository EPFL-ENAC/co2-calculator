import { computed, watch, type Ref } from 'vue';
import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  type AllSubmoduleTypes,
  type Module,
} from 'src/constant/modules';
import { useBuildingRoomStore } from 'src/stores/building_rooms';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useModuleStore } from 'src/stores/modules';

type FormLike = Record<string, unknown>;

function strOrNull(v: unknown): string | null {
  return typeof v === 'string' && v !== '' ? v : null;
}

export function useBuildingRoomDynamicOptions(
  form: FormLike,
  moduleType: Ref<Module | string>,
  submoduleType: Ref<AllSubmoduleTypes>,
  unitId: Ref<number | undefined>,
) {
  const workspaceStore = useWorkspaceStore();
  const buildingRoomStore = useBuildingRoomStore();
  const moduleStore = useModuleStore();
  let roomDetailsRequestId = 0;

  const isBuildingsRoomSubmodule = computed(
    () =>
      moduleType.value === MODULES.Buildings &&
      submoduleType.value === SUBMODULE_BUILDINGS_TYPES.Building,
  );

  // Buildings from taxonomy (no API call — taxonomy fetched by ModuleTable)
  const buildingOptions = computed(() => {
    if (!isBuildingsRoomSubmodule.value) return [];
    const taxo =
      moduleStore.state.taxonomySubmodule[String(submoduleType.value)];
    return (
      taxo?.children?.map((n) => ({ value: n.name, label: n.label })) ?? []
    );
  });

  // Rooms filtered by selected building (sync, no API call)
  const buildingRoomOptions = computed(() => {
    if (!isBuildingsRoomSubmodule.value) return [];
    const buildingName = strOrNull(form['building_name']);
    if (!buildingName) return [];
    const taxo =
      moduleStore.state.taxonomySubmodule[String(submoduleType.value)];
    const buildingNode = taxo?.children?.find((n) => n.name === buildingName);
    return (
      buildingNode?.children?.map((n) => ({ value: n.name, label: n.label })) ??
      []
    );
  });

  const dynamicOptionsById = computed<
    Record<string, Array<{ value: string; label: string }>>
  >(() => {
    if (!isBuildingsRoomSubmodule.value) return {};
    return {
      kind: buildingOptions.value,
      subkind: buildingRoomOptions.value,
    };
  });

  // Loading state tied to taxonomy presence (undefined = still fetching)
  const loadingByOptionsId = computed<Record<string, boolean>>(() => {
    const taxo =
      moduleStore.state.taxonomySubmodule[String(submoduleType.value)];
    const loading = taxo === undefined;
    return Object.fromEntries(
      Object.keys(dynamicOptionsById.value).map((key) => [key, loading]),
    );
  });

  // Clear room fields when building changes
  watch(
    () => form['building_name'],
    (newValue, oldValue) => {
      const oldBuilding = strOrNull(oldValue);
      const newBuilding = strOrNull(newValue);
      if (!oldBuilding || !newBuilding || oldBuilding === newBuilding) return;
      const currentRoomName = strOrNull(form['room_name']);
      const roomStillValid = buildingRoomOptions.value.some(
        (opt) => opt.value === currentRoomName,
      );
      if (!roomStillValid) {
        form['room_name'] = null;
        form['room_surface_square_meter'] = null;
        form['room_type'] = null;
      }
    },
  );

  // Async watch: room_name → auto-fill surface and room_type from reference
  watch(
    () => form['room_name'],
    async (newVal, oldVal) => {
      const requestId = ++roomDetailsRequestId;
      if (!isBuildingsRoomSubmodule.value) return;
      const roomName = strOrNull(newVal);
      const oldRoomName = strOrNull(oldVal);
      if (!roomName || roomName === oldRoomName) return;

      const buildingName = strOrNull(form['building_name']);
      if (!buildingName) return;

      const currentUnitId = unitId.value ?? workspaceStore.selectedUnit?.id;
      if (!currentUnitId) return;

      try {
        const rooms = await buildingRoomStore.fetchRooms(
          currentUnitId,
          buildingName,
        );
        if (requestId !== roomDetailsRequestId) return;
        if (form['building_name'] !== buildingName) return;
        if (form['room_name'] !== roomName) return;
        const comparableRoomName = roomName.trim().toLowerCase();
        const match = rooms.find(
          (r) => r.room_name.trim().toLowerCase() === comparableRoomName,
        );
        if (!match) return;

        form['room_type'] = match.room_type ?? null;
        form['room_surface_square_meter'] = match.room_surface_square_meter;
      } catch {
        // Room lookup is best-effort; users can still fill values manually.
      }
    },
  );

  return {
    buildingOptions,
    buildingRoomOptions,
    dynamicOptionsById,
    loadingByOptionsId,
  };
}
