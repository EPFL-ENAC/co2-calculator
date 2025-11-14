import { boot } from 'quasar/wrappers';
import { useWorkspaceStore } from 'src/stores/workspace';

export default boot(async () => {
  const workspaceStore = useWorkspaceStore();
  // Initialize workspace (unit/year) from cookies if available
  await workspaceStore.initFromCookies();
});
