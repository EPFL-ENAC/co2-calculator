import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { type Module } from 'src/constant/modules';

export function useUnifiedModuleConfig() {
  const route = useRoute();
  const yearConfigStore = useYearConfigStore();

  const currentModule = computed(
    () => route.params.module as Module | undefined,
  );

  const currentUnifiedConfig = computed(() => {
    if (!currentModule.value) return null;
    return yearConfigStore.getModule(currentModule.value);
  });

  const getSubmodule = (subKey: string) => {
    if (!currentModule.value) return null;
    return yearConfigStore.getSubmodule(currentModule.value, subKey);
  };

  return {
    currentModule,
    currentUnifiedConfig,
    getSubmodule,
  };
}
