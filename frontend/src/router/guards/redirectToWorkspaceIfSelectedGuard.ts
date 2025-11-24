import { RouteLocationNormalized } from 'vue-router';
import { useWorkspaceStore } from 'src/stores/workspace';
import {
  WORKSPACE_ROUTE_NAME,
  WORKSPACE_SETUP_ROUTE_NAME,
  LOGIN_ROUTE_NAME,
} from '../routes';

export default async function redirectToWorkspaceIfSelectedGuard(
  to: RouteLocationNormalized,
) {
  const workspaceStore = useWorkspaceStore();

  // Always allow access to workspace-setup and login pages
  if (to.name === WORKSPACE_SETUP_ROUTE_NAME || to.name === LOGIN_ROUTE_NAME) {
    return true;
  }

  // For all other routes, require workspace to be selected
  // If not selected, redirect to workspace-setup
  if (!workspaceStore.selectedUnit || !workspaceStore.selectedYear) {
    return {
      name: WORKSPACE_SETUP_ROUTE_NAME,
      params: {
        language: to.params.language,
      },
    };
  }

  // Workspace is selected, allow navigation
  return true;
}
