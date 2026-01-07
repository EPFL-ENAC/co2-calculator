import { useTimelineStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

async function validateUnit() {
  const workspaceStore = useWorkspaceStore();
  const routeUnit = String(workspaceStore.selectedParams?.unit || '');
  const unitIdFromRoute = routeUnit.split('-')[0];
  const validUnit = workspaceStore.units.find(
    (unit) => unit.id === unitIdFromRoute || unit.name === routeUnit,
  );

  if (validUnit) {
    workspaceStore.setUnit(validUnit);
    workspaceStore.setYear(workspaceStore.selectedParams?.year || null);
    return true;
  }
  // If the unit from the route is not valid, redirect to workspace setup
  workspaceStore.setUnit(null);
  workspaceStore.setYear(null);
  // go back to workspcae-setup
  return false;
}

export default async function validateUnitGuard(to) {
  // redirectToWorkspaceIfNotSelectedGuard
  useWorkspaceStore().setSelectedParams({
    year: parseInt(to.params.year as string, 10),
    unit: to.params.unit as string,
  });
  const workspaceStore = useWorkspaceStore();
  await workspaceStore.getUnits();
  const response = await validateUnit();
  // if unit is valid retrieve inventory!
  let inventoryId = null;
  if (response) {
    await workspaceStore.selectInventoryForYear(
      workspaceStore.selectedUnit.id,
      workspaceStore.selectedYear,
    );
    inventoryId = workspaceStore.selectedInventory?.id;
    if (inventoryId) {
      const timelineStore = useTimelineStore();
      await timelineStore.fetchModuleStates(inventoryId);
    }
  }
  // then we can retrieve modules
  if (!response && !inventoryId) {
    return {
      name: 'workspace-setup',
      params: {
        language: to.params.language || 'en',
      },
      query: {
        unit: null,
        year: null,
      },
    };
  }
  return true;
}
