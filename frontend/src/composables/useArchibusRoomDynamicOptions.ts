import { computed, watch, type Ref } from 'vue';
import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  type AllSubmoduleTypes,
  type Module,
} from 'src/constant/modules';
import { useArchibusRoomStore } from 'src/stores/archibus';
import { useWorkspaceStore } from 'src/stores/workspace';

type FormLike = Record<string, unknown>;

export function useArchibusRoomDynamicOptions(
  form: FormLike,
  moduleType: Ref<Module | string>,
  submoduleType: Ref<AllSubmoduleTypes>,
  unitId: Ref<number | undefined>,
) {
  const workspaceStore = useWorkspaceStore();
  const archibusStore = useArchibusRoomStore();

  const isBuildingsRoomSubmodule = computed(
    () =>
      moduleType.value === MODULES.Buildings &&
      submoduleType.value === SUBMODULE_BUILDINGS_TYPES.Building,
  );

  watch(
    () => form['room_name'],
    async (newVal, oldVal) => {
      if (!isBuildingsRoomSubmodule.value) return;
      if (!newVal || newVal === oldVal) return;

      const buildingName = form['building_name'];
      if (!buildingName || typeof buildingName !== 'string') return;

      const currentUnitId = unitId.value ?? workspaceStore.selectedUnit?.id;
      if (!currentUnitId) return;

      try {
        const rooms = await archibusStore.fetchRooms(
          currentUnitId,
          buildingName,
        );
        const match = rooms.find((r) => r.room_name === newVal);
        if (!match) return;

        form['room_type'] = match.room_type ?? '';
        form['room_surface_square_meter'] = match.room_surface_square_meter;
        form['heating_kwh_per_square_meter'] =
          match.heating_kwh_per_square_meter ?? 0;
        form['cooling_kwh_per_square_meter'] =
          match.cooling_kwh_per_square_meter ?? 0;
        form['ventilation_kwh_per_square_meter'] =
          match.ventilation_kwh_per_square_meter ?? 0;
        form['lighting_kwh_per_square_meter'] =
          match.lighting_kwh_per_square_meter ?? 0;
      } catch {
        // Archibus lookup is best-effort; users can still fill values manually.
      }
    },
  );
}
