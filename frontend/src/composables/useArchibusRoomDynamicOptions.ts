import { computed, ref, watch, type Ref } from 'vue';
import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  type AllSubmoduleTypes,
  type Module,
} from 'src/constant/modules';
import { useArchibusRoomStore } from 'src/stores/archibus';
import { useWorkspaceStore } from 'src/stores/workspace';

type FormLike = Record<string, unknown>;

function normalizeSelectValue(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'object' && value && 'value' in value) {
    const inner = (value as { value?: unknown }).value;
    return inner === null || inner === undefined || inner === ''
      ? null
      : String(inner);
  }
  return String(value);
}

function toComparable(value: string): string {
  return value.trim().toLowerCase();
}

function parseNumericValue(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;

  const normalized = String(value).trim().replace(/,/g, '');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function useArchibusRoomDynamicOptions(
  form: FormLike,
  moduleType: Ref<Module | string>,
  submoduleType: Ref<AllSubmoduleTypes>,
  unitId: Ref<number | undefined>,
) {
  const workspaceStore = useWorkspaceStore();
  const archibusStore = useArchibusRoomStore();
  const archibusBuildingOptions = ref<Array<{ value: string; label: string }>>(
    [],
  );
  const archibusRoomOptions = ref<Array<{ value: string; label: string }>>([]);
  const loadingArchibusBuildings = ref(false);
  const loadingArchibusRooms = ref(false);

  const isBuildingsRoomSubmodule = computed(
    () =>
      moduleType.value === MODULES.Buildings &&
      submoduleType.value === SUBMODULE_BUILDINGS_TYPES.Building,
  );

  const dynamicOptionsById = computed<
    Record<string, Array<{ value: string; label: string }>>
  >(() => {
    if (!isBuildingsRoomSubmodule.value) return {};
    return {
      kind: archibusBuildingOptions.value,
      subkind: archibusRoomOptions.value,
    };
  });

  const loadingByOptionsId = computed<Record<string, boolean>>(() => {
    if (!isBuildingsRoomSubmodule.value) return {};
    return {
      kind: loadingArchibusBuildings.value,
      subkind: loadingArchibusRooms.value,
    };
  });

  watch(
    [isBuildingsRoomSubmodule, unitId, () => workspaceStore.selectedUnit?.id],
    async () => {
      if (!isBuildingsRoomSubmodule.value) {
        archibusBuildingOptions.value = [];
        return;
      }

      const currentUnitId = unitId.value ?? workspaceStore.selectedUnit?.id;
      if (!currentUnitId) {
        archibusBuildingOptions.value = [];
        return;
      }

      loadingArchibusBuildings.value = true;
      try {
        const buildings = await archibusStore.fetchBuildings(currentUnitId);
        archibusBuildingOptions.value = buildings.map((building) => ({
          value: building.building_name,
          label: building.building_name,
        }));
      } finally {
        loadingArchibusBuildings.value = false;
      }
    },
    { immediate: true },
  );

  watch(
    () => form['building_name'],
    async (newValue, oldValue) => {
      if (!isBuildingsRoomSubmodule.value) return;

      const buildingName = normalizeSelectValue(form['building_name']);
      const currentUnitId = unitId.value ?? workspaceStore.selectedUnit?.id;
      if (!buildingName || !currentUnitId) {
        archibusRoomOptions.value = [];
        return;
      }

      loadingArchibusRooms.value = true;
      try {
        const rooms = await archibusStore.fetchRooms(currentUnitId, buildingName);
        archibusRoomOptions.value = rooms.map((room) => ({
          value: room.room_name,
          label: room.room_name,
        }));

        const oldBuildingName = normalizeSelectValue(oldValue);
        const newBuildingName = normalizeSelectValue(newValue);
        if (oldBuildingName && newBuildingName && oldBuildingName !== newBuildingName) {
          const currentRoomName = normalizeSelectValue(form['room_name']);
          const roomStillValid = archibusRoomOptions.value.some(
            (roomOption) => roomOption.value === currentRoomName,
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
        }
      } finally {
        loadingArchibusRooms.value = false;
      }
    },
    { immediate: true },
  );

  watch(
    () => form['room_name'],
    async (newVal, oldVal) => {
      if (!isBuildingsRoomSubmodule.value) return;
      const roomName = normalizeSelectValue(newVal);
      const oldRoomName = normalizeSelectValue(oldVal);
      if (!roomName || roomName === oldRoomName) return;

      const buildingName = normalizeSelectValue(form['building_name']);
      if (!buildingName) return;

      const currentUnitId = unitId.value ?? workspaceStore.selectedUnit?.id;
      if (!currentUnitId) return;

      try {
        const rooms = await archibusStore.fetchRooms(
          currentUnitId,
          buildingName,
        );
        const comparableRoomName = toComparable(roomName);
        const match = rooms.find(
          (r) => toComparable(String(r.room_name)) === comparableRoomName,
        );
        if (!match) return;

        form['room_type'] = match.room_type ?? null;
        const surface = parseNumericValue(match.room_surface_square_meter);
        const heatingPerSquareMeter =
          parseNumericValue(match.heating_kwh_per_square_meter) ?? 0;
        const coolingPerSquareMeter =
          parseNumericValue(match.cooling_kwh_per_square_meter) ?? 0;
        const ventilationPerSquareMeter =
          parseNumericValue(match.ventilation_kwh_per_square_meter) ?? 0;
        const lightingPerSquareMeter =
          parseNumericValue(match.lighting_kwh_per_square_meter) ?? 0;

        form['room_surface_square_meter'] = surface;
        form['heating_kwh_per_square_meter'] = heatingPerSquareMeter;
        form['cooling_kwh_per_square_meter'] = coolingPerSquareMeter;
        form['ventilation_kwh_per_square_meter'] = ventilationPerSquareMeter;
        form['lighting_kwh_per_square_meter'] = lightingPerSquareMeter;
        form['heating_kwh'] = surface === null ? null : heatingPerSquareMeter * surface;
        form['cooling_kwh'] = surface === null ? null : coolingPerSquareMeter * surface;
        form['ventilation_kwh'] =
          surface === null ? null : ventilationPerSquareMeter * surface;
        form['lighting_kwh'] = surface === null ? null : lightingPerSquareMeter * surface;
      } catch {
        // Archibus lookup is best-effort; users can still fill values manually.
      }
    },
  );

  return {
    archibusBuildingOptions,
    archibusRoomOptions,
    loadingArchibusBuildings,
    loadingArchibusRooms,
    dynamicOptionsById,
    loadingByOptionsId,
  };
}
