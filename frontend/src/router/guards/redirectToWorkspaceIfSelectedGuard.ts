import { useWorkspaceStore } from 'src/stores/workspace';
import { WORKSPACE_ROUTE_NAME, WORKSPACE_SETUP_ROUTE_NAME } from '../routes';

export default async function redirectToWorkspaceIfSelectedGuard(to) {
  const workspaceStore = useWorkspaceStore();

  // Always allow access to workspace-setup page (users can change their workspace)
  if (to.name === WORKSPACE_SETUP_ROUTE_NAME) {
    return true;
  }

  // For other routes, if workspace is selected, redirect to workspace
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
