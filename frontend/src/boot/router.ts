import { defineBoot } from '#q-app';
import { getActivePinia } from 'pinia';

export default defineBoot(({ router }) => {
  // Get the active Pinia instance
  const pinia = getActivePinia();

  if (pinia) {
    // Inject router into all stores
    pinia.use(() => ({ router }));
  }
});
