import { boot } from 'quasar/wrappers';
import { useWorkspaceStore } from 'src/stores/workspace';

export default boot(async () => {
  const workspaceStore = useWorkspaceStore();
  // Initialize workspace (unit/year) from persisted state if available
  await workspaceStore.initFromPersisted();
});
