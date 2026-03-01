import { computed, watch, type Ref } from 'vue';
import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  type AllSubmoduleTypes,
  type Module,
} from 'src/constant/modules';
import { useArchibusRoomStore } from 'src/stores/archibus';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useModuleStore } from 'src/stores/modules';

type FormLike = Record<string, unknown>;

function strOrNull(v: unknown): string | null {
  return typeof v === 'string' && v !== '' ? v : null;
}

export function useArchibusRoomDynamicOptions(
  form: FormLike,
  moduleType: Ref<Module | string>,
  submoduleType: Ref<AllSubmoduleTypes>,
  unitId: Ref<number | undefined>,
) {
  const workspaceStore = useWorkspaceStore();
  const archibusStore = useArchibusRoomStore();
  const moduleStore = useModuleStore();
  let roomDetailsRequestId = 0;

  const isBuildingsRoomSubmodule = computed(
    () =>
      moduleType.value === MODULES.Buildings &&
      submoduleType.value === SUBMODULE_BUILDINGS_TYPES.Building,
  );

  // Buildings from taxonomy (no API call — taxonomy fetched by ModuleTable)
  const archibusBuildingOptions = computed(() => {
    if (!isBuildingsRoomSubmodule.value) return [];
    const taxo =
      moduleStore.state.taxonomySubmodule[String(submoduleType.value)];
    return (
      taxo?.children?.map((n) => ({ value: n.name, label: n.label })) ?? []
    );
  });

  // Rooms filtered by selected building (sync, no API call)
  const archibusRoomOptions = computed(() => {
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
      kind: archibusBuildingOptions.value,
      subkind: archibusRoomOptions.value,
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

  // Clear room fields when building changes (sync — options are a computed)
  watch(
    () => form['building_name'],
    (newValue, oldValue) => {
      const oldBuilding = strOrNull(oldValue);
      const newBuilding = strOrNull(newValue);
      if (!oldBuilding || !newBuilding || oldBuilding === newBuilding) return;
      const currentRoomName = strOrNull(form['room_name']);
      const roomStillValid = archibusRoomOptions.value.some(
        (opt) => opt.value === currentRoomName,
      );
      if (!roomStillValid) {
        form['room_name'] = null;
        form['room_surface_square_meter'] = null;
        form['room_type'] = null;
        form['heating_kwh'] = null;
        form['cooling_kwh'] = null;
        form['ventilation_kwh'] = null;
        form['lighting_kwh'] = null;
      }
    },
  );

  // Async watch: room_name → auto-fill surface/kWh from Archibus
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
        const rooms = await archibusStore.fetchRooms(
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

        const surface = match.room_surface_square_meter;
        const heatingPerSquareMeter = match.heating_kwh_per_square_meter;
        const coolingPerSquareMeter = match.cooling_kwh_per_square_meter;
        const ventilationPerSquareMeter =
          match.ventilation_kwh_per_square_meter;
        const lightingPerSquareMeter = match.lighting_kwh_per_square_meter;

        form['room_type'] = match.room_type ?? null;
        form['room_surface_square_meter'] = surface;
        form['heating_kwh_per_square_meter'] = heatingPerSquareMeter;
        form['cooling_kwh_per_square_meter'] = coolingPerSquareMeter;
        form['ventilation_kwh_per_square_meter'] = ventilationPerSquareMeter;
        form['lighting_kwh_per_square_meter'] = lightingPerSquareMeter;
        form['heating_kwh'] =
          surface === null ? null : heatingPerSquareMeter * surface;
        form['cooling_kwh'] =
          surface === null ? null : coolingPerSquareMeter * surface;
        form['ventilation_kwh'] =
          surface === null ? null : ventilationPerSquareMeter * surface;
        form['lighting_kwh'] =
          surface === null ? null : lightingPerSquareMeter * surface;
      } catch {
        // Archibus lookup is best-effort; users can still fill values manually.
      }
    },
  );

  return {
    archibusBuildingOptions,
    archibusRoomOptions,
    dynamicOptionsById,
    loadingByOptionsId,
  };
}
