import { boot } from 'quasar/wrappers';
import { getActivePinia } from 'pinia';

export default boot(({ router }) => {
  // Get the active Pinia instance
  const pinia = getActivePinia();
  
  if (pinia) {
    // Inject router into all stores
    pinia.use(({ store }) => {
      store.$router = router;
    });
  }
});

