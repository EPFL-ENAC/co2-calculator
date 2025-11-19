import { useWorkspaceStore } from 'src/stores/workspace';
import { WORKSPACE_ROUTE_NAME } from '../routes';

export default async function redirectToWorkspaceIfSelectedGuard(to) {
  const workspaceStore = useWorkspaceStore();
  if (workspaceStore.selectedUnit && workspaceStore.selectedYear) {
    const unit = encodeURIComponent(workspaceStore.selectedUnit.name);
    const year = workspaceStore.selectedYear;
    return {
      name: WORKSPACE_ROUTE_NAME,
      params: {
        language: to.params.language,
        unit,
        year,
      },
    };
  }
  // If no redirect, just allow navigation
  return true;
}
