import { reactive, ref, watch, type Ref } from 'vue';
import { usePowerFactorsStore } from 'src/stores/powerFactors';

type Option = { label: string; value: string };

type SubmoduleType = 'scientific' | 'it' | 'other' | undefined;

interface FieldConfig {
  classFieldId?: string;
  subClassFieldId?: string;
  actPowerFieldId?: string;
  pasPowerFieldId?: string;
}

export function useModulePowerFactors<TEntity extends Record<string, unknown>>(
  entity: TEntity,
  submoduleType: Ref<SubmoduleType>,
  config: FieldConfig = {},
) {
  const classFieldId = config.classFieldId ?? 'class';
  const subClassFieldId = config.subClassFieldId ?? 'sub_class';
  const actPowerFieldId = config.actPowerFieldId ?? 'act_power';
  const pasPowerFieldId = config.pasPowerFieldId ?? 'pas_power';

  const dynamicOptions = reactive<Record<string, Option[]>>({});
  const loadingClasses = ref(false);
  const loadingSubclasses = ref(false);
  const loadingPowerFactor = ref(false);
  const subclassLoadError = ref(false);

  const store = usePowerFactorsStore();

  function normalizeValue(raw: unknown): string | null {
    if (raw === null || raw === undefined || raw === '') return null;
    if (typeof raw === 'object' && 'value' in (raw as Option)) {
      return String((raw as Option).value);
    }
    return String(raw);
  }

  async function loadClassOptions() {
    const sub = submoduleType.value;
    if (!sub) return;
    loadingClasses.value = true;
    try {
      dynamicOptions[classFieldId] = await store.fetchClassOptions(sub);
    } catch {
      dynamicOptions[classFieldId] = [];
    } finally {
      loadingClasses.value = false;
    }
  }

  async function loadSubclassOptions() {
    const sub = submoduleType.value;
    const cls = normalizeValue(entity[classFieldId]);
    if (!sub || !cls) {
      dynamicOptions[subClassFieldId] = [];
      subclassLoadError.value = false;
      return;
    }
    loadingSubclasses.value = true;
    subclassLoadError.value = false;
    try {
      const options = await store.fetchSubclassOptions(sub, cls);

      // Ensure the currently selected subclass (if any) is present in the
      // options, even if the backend map does not include it (for example
      // when legacy data has subclasses but no dedicated power-factor row).
      const currentSub = normalizeValue(entity[subClassFieldId]);
      if (
        currentSub &&
        !options.some((opt) => String(opt.value) === String(currentSub))
      ) {
        options.push({ label: currentSub, value: currentSub });
      }

      dynamicOptions[subClassFieldId] = options;
    } catch {
      const fallback: Option[] = [];
      const currentSub = normalizeValue(entity[subClassFieldId]);
      if (currentSub) {
        fallback.push({ label: currentSub, value: currentSub });
      }
      dynamicOptions[subClassFieldId] = fallback;
      subclassLoadError.value = true;
    } finally {
      loadingSubclasses.value = false;
    }
  }

  async function loadPowerFactor() {
    const sub = submoduleType.value;
    if (!sub) return;

    const cls = normalizeValue(entity[classFieldId]);
    if (!cls) return;

    const subCls = normalizeValue(entity[subClassFieldId]);

    loadingPowerFactor.value = true;
    try {
      const pf = await store.fetchPowerFactor(sub, cls, subCls);
      if (pf) {
        if (actPowerFieldId in entity)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity as any)[actPowerFieldId] = pf.active_power_w;
        if (pasPowerFieldId in entity)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity as any)[pasPowerFieldId] = pf.standby_power_w;
      }
    } catch {
      // ignore, user can still fill manually
    } finally {
      loadingPowerFactor.value = false;
    }
  }

  function resetDerivedFields() {
    if (subClassFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[subClassFieldId] = '';
    if (actPowerFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[actPowerFieldId] = null;
    if (pasPowerFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[pasPowerFieldId] = null;
  }

  // React to submodule type changes
  let submoduleInitialized = false;
  watch(
    submoduleType,
    async () => {
      if (!submoduleType.value) {
        dynamicOptions[classFieldId] = [];
        dynamicOptions[subClassFieldId] = [];
        resetDerivedFields();
        return;
      }

      await loadClassOptions();

      // On first initialization, keep existing subclass/power values so
      // editing an existing row doesn't lose data. On subsequent
      // submodule changes, clear derived fields.
      if (submoduleInitialized) {
        dynamicOptions[subClassFieldId] = [];
        resetDerivedFields();
      }

      submoduleInitialized = true;
    },
    { immediate: true },
  );

  // When class changes, refresh subclasses and power factor
  watch(
    () => entity[classFieldId],
    async (newVal, oldVal) => {
      await loadSubclassOptions();

      // If the class has changed after initialization, clear
      // subclass/power so the user explicitly re-selects.
      if (submoduleInitialized && oldVal !== null && newVal !== oldVal) {
        if (subClassFieldId in entity)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity as any)[subClassFieldId] = '';
        resetDerivedFields();
      }

      await loadPowerFactor();
    },
    { immediate: true },
  );

  // When subclass changes, refresh power factor
  watch(
    () => entity[subClassFieldId],
    async () => {
      await loadPowerFactor();
    },
  );

  return {
    dynamicOptions,
    loadingClasses,
    loadingSubclasses,
    loadingPowerFactor,
    subclassLoadError,
    loadClassOptions,
    loadSubclassOptions,
    loadPowerFactor,
    resetDerivedFields,
  };
}
