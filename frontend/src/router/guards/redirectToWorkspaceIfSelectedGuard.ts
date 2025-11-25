import { useWorkspaceStore } from 'src/stores/workspace';
import {
  HOME_ROUTE_NAME,
  WORKSPACE_SETUP_ROUTE_NAME,
  LOGIN_ROUTE_NAME,
} from '../routes';

export default async function redirectToWorkspaceIfSelectedGuard(to) {
  const workspaceStore = useWorkspaceStore();

  // Always allow access to login and workspace
  if (to.name === WORKSPACE_SETUP_ROUTE_NAME || to.name === LOGIN_ROUTE_NAME) {
    return true;
  }

  // If workspace unit and year are selectd -> home
  if (
    workspaceStore.selectedUnit &&
    workspaceStore.selectedYear &&
    to.name === WORKSPACE_SETUP_ROUTE_NAME
  ) {
    const unit = encodeURIComponent(workspaceStore.selectedUnit.name);
    const year = workspaceStore.selectedYear;
    return {
      name: HOME_ROUTE_NAME,
      params: {
        language: to.params.language,
        unit,
        year,
      },
    };
  }

  // If workspace is not selected and not already on workspace setup -> Worspace Setup
  if (
    (!workspaceStore.selectedUnit || !workspaceStore.selectedYear) &&
    to.name !== WORKSPACE_SETUP_ROUTE_NAME
  ) {
    return {
      name: WORKSPACE_SETUP_ROUTE_NAME,
      params: {
        language: to.params.language,
      },
    };
  }

  return true;
}
