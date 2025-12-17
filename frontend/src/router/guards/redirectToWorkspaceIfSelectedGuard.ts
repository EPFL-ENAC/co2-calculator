import { useWorkspaceStore } from 'src/stores/workspace';
import { HOME_ROUTE_NAME } from '../routes';

export default async function redirectToWorkspaceIfSelectedGuard(to) {
  const workspaceStore = useWorkspaceStore();
  // If workspace unit and year are selectd -> home
  if (to.query.unit === null && to.query.year === null) {
    workspaceStore.reset();
    return true;
  }
  if (workspaceStore.selectedParams) {
    return {
      name: HOME_ROUTE_NAME,
      params: {
        ...to.params,
        unit: encodeURIComponent(workspaceStore.selectedParams.unit),
        year: workspaceStore.selectedParams.year,
      },
    };
  }

  return true;
}
