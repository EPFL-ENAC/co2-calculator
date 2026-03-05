import { computed, reactive, watch, type Ref } from 'vue';
import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  type AllSubmoduleTypes,
  type Module,
} from 'src/constant/modules';
import { useBuildingRoomStore } from 'src/stores/building_rooms';

type FormLike = Record<string, unknown>;

export function useBuildingRoomDynamicOptions(
  form: FormLike,
  moduleType: Ref<Module | string>,
  submoduleType: Ref<AllSubmoduleTypes>,
) {
  const buildingRoomStore = useBuildingRoomStore();

  const dynamicOptions = reactive<
    Record<string, Array<{ value: string; label: string }>>
  >({});
  let buildingRoomsRequestId = 0;
  let roomSelectionRequestId = 0;
  let energyDefaultsRequestId = 0;

  const isBuildingsRoomSubmodule = computed(
    () =>
      moduleType.value === MODULES.Buildings &&
      submoduleType.value === SUBMODULE_BUILDINGS_TYPES.Building,
  );

  // When building_name changes: fetch room options and clear dependent fields
  watch(
    () => form['building_name'],
    async (newVal, oldVal) => {
      if (!isBuildingsRoomSubmodule.value) return;
      if (!newVal || typeof newVal !== 'string') {
        dynamicOptions['subkind'] = [];
        form['room_name'] = null;
        form['room_type'] = null;
        form['room_surface_square_meter'] = null;
        form['heating_kwh_per_square_meter'] = null;
        form['cooling_kwh_per_square_meter'] = null;
        form['ventilation_kwh_per_square_meter'] = null;
        form['lighting_kwh_per_square_meter'] = null;
        return;
      }

      // Clear dependent fields when building changes
      if (oldVal && newVal !== oldVal) {
        form['room_name'] = null;
        form['room_type'] = null;
        form['room_surface_square_meter'] = null;
        form['heating_kwh_per_square_meter'] = null;
        form['cooling_kwh_per_square_meter'] = null;
        form['ventilation_kwh_per_square_meter'] = null;
        form['lighting_kwh_per_square_meter'] = null;
      }

      try {
        const requestId = ++buildingRoomsRequestId;
        const rooms = await buildingRoomStore.fetchRooms(newVal);
        if (requestId !== buildingRoomsRequestId) return;
        dynamicOptions['subkind'] = rooms.map((r) => ({
          value: r.room_name,
          label: r.room_name,
        }));
      } catch {
        dynamicOptions['subkind'] = [];
      }
    },
    { immediate: true },
  );

  let suppressNextRoomTypeWatcher = false;

  async function refetchEnergyDefaults(buildingName: string, roomType: string) {
    const requestId = ++energyDefaultsRequestId;
    form['heating_kwh_per_square_meter'] = null;
    form['cooling_kwh_per_square_meter'] = null;
    form['ventilation_kwh_per_square_meter'] = null;
    form['lighting_kwh_per_square_meter'] = null;

    const defaults = await buildingRoomStore.fetchEnergyDefaults(
      buildingName,
      roomType.trim().toLowerCase(),
    );
    if (requestId !== energyDefaultsRequestId) return;

    form['heating_kwh_per_square_meter'] =
      defaults.heating_kwh_per_square_meter;
    form['cooling_kwh_per_square_meter'] =
      defaults.cooling_kwh_per_square_meter;
    form['ventilation_kwh_per_square_meter'] =
      defaults.ventilation_kwh_per_square_meter;
    form['lighting_kwh_per_square_meter'] =
      defaults.lighting_kwh_per_square_meter;
  }

  // When room_name changes: fill room_type + room_surface + kwh/m² fields
  watch(
    () => form['room_name'],
    async (newVal, oldVal) => {
      if (!isBuildingsRoomSubmodule.value) return;
      if (!newVal || newVal === oldVal) return;

      const buildingName = form['building_name'];
      if (!buildingName || typeof buildingName !== 'string') return;

      try {
        const requestId = ++roomSelectionRequestId;
        const rooms = await buildingRoomStore.fetchRooms(buildingName);
        if (requestId !== roomSelectionRequestId) return;
        const match = rooms.find((r) => r.room_name === newVal);
        if (!match) return;

        suppressNextRoomTypeWatcher = true;
        try {
          form['room_type'] = match.room_type
            ? match.room_type.trim().toLowerCase()
            : null;
          form['room_surface_square_meter'] = match.room_surface_square_meter;

          const roomType = match.room_type
            ? match.room_type.trim().toLowerCase()
            : null;
          if (!roomType) return;
          await refetchEnergyDefaults(buildingName, roomType);
        } finally {
          suppressNextRoomTypeWatcher = false;
        }
      } catch {
        // Building room lookup is best-effort; users can still fill values manually.
      }
    },
  );

  // When room_type changes manually: re-fetch energy defaults
  watch(
    () => form['room_type'],
    async (newVal, oldVal) => {
      if (suppressNextRoomTypeWatcher) {
        suppressNextRoomTypeWatcher = false;
        return;
      }
      if (!isBuildingsRoomSubmodule.value) return;
      if (!newVal || newVal === oldVal || typeof newVal !== 'string') return;

      const buildingName = form['building_name'];
      if (!buildingName || typeof buildingName !== 'string') return;

      try {
        await refetchEnergyDefaults(buildingName, newVal.trim().toLowerCase());
      } catch {
        // Best-effort
      }
    },
  );

  return { dynamicOptions };
}
