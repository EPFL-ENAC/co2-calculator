import { reactive, ref, watch, type Ref } from 'vue';
import { useFactorsStore } from 'src/stores/factors';
import type { AllSubmoduleTypes } from 'src/constant/modules';

type Option = { label: string; value: string };

interface FieldConfig {
  classFieldId?: string;
  subClassFieldId?: string;
  classOptionId?: string;
  subClassOptionId?: string;
  primaryValueFieldId?: string;
  secondaryValueFieldId?: string;
  fetchFactorValuesOnChange?: boolean;
}

export function useEquipmentClassOptions<TEntity extends Record<string, unknown>>(
  entity: TEntity,
  submoduleType: Ref<AllSubmoduleTypes>,
  config: FieldConfig = {},
) {
  const classFieldId = config.classFieldId ?? '';
  const subClassFieldId = config.subClassFieldId ?? '';

  const classOptionId = config.classOptionId ?? 'kind';
  const subClassOptionId = config.subClassOptionId ?? 'subkind';
  const primaryValueFieldId = config.primaryValueFieldId ?? '';
  const secondaryValueFieldId = config.secondaryValueFieldId ?? '';

  const fetchFactorValuesOnChange = config.fetchFactorValuesOnChange ?? false;

  const dynamicOptions = reactive<Record<string, Option[]>>({});
  const loadingClasses = ref(false);
  const loadingSubclasses = ref(false);
  const loadingPowerFactor = ref(false);
  const subclassLoadError = ref(false);

  const store = useFactorsStore();

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
      dynamicOptions[classOptionId] = await store.fetchClassOptions(sub);
    } catch {
      dynamicOptions[classOptionId] = [];
    } finally {
      loadingClasses.value = false;
    }
  }

  async function loadSubclassOptions() {
    const sub = submoduleType.value;
    const cls = normalizeValue(entity[classFieldId]);
    if (!sub || !cls) {
      dynamicOptions[subClassOptionId] = [];
      subclassLoadError.value = false;
      return;
    }
    loadingSubclasses.value = true;
    subclassLoadError.value = false;
    try {
      const options = await store.fetchSubclassOptions(sub, cls);
      const currentSub = normalizeValue(entity[subClassFieldId]);
      if (
        currentSub &&
        !options.some((opt) => String(opt.value) === String(currentSub))
      ) {
        options.push({ label: currentSub, value: currentSub });
      }
      dynamicOptions[subClassOptionId] = options;
    } catch {
      const fallback: Option[] = [];
      const currentSub = normalizeValue(entity[subClassFieldId]);
      if (currentSub) {
        fallback.push({ label: currentSub, value: currentSub });
      }
      dynamicOptions[subClassOptionId] = fallback;
      subclassLoadError.value = true;
    } finally {
      loadingSubclasses.value = false;
    }
  }

  function subclassRequired(): boolean {
    const options = dynamicOptions[subClassOptionId];
    return Array.isArray(options) && options.length > 0;
  }

  async function loadPowerFactor() {
    const sub = submoduleType.value;
    if (!sub) return;

    const cls = normalizeValue(entity[classFieldId]);
    if (!cls) return;

    const subCls = normalizeValue(entity[subClassFieldId]);
    if (subclassRequired() && !subCls) {
      return;
    }

    loadingPowerFactor.value = true;
    try {
      const pf = await store.fetchPowerFactor(sub, cls, subCls);
      if (pf) {
        if (primaryValueFieldId && primaryValueFieldId in entity)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity as any)[primaryValueFieldId] = pf[primaryValueFieldId];
        if (secondaryValueFieldId && secondaryValueFieldId in entity)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity as any)[secondaryValueFieldId] = pf[secondaryValueFieldId];
      }
    } catch {
      // ignore, user can still fill manually
    } finally {
      loadingPowerFactor.value = false;
    }
  }

  function resetSubclass() {
    if (subClassFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[subClassFieldId] = '';
    if (primaryValueFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[primaryValueFieldId] = null;
    if (secondaryValueFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[secondaryValueFieldId] = null;
  }

  let submoduleInitialized = false;
  watch(
    submoduleType,
    async () => {
      if (!submoduleType.value) {
        dynamicOptions[classOptionId] = [];
        dynamicOptions[subClassOptionId] = [];
        resetSubclass();
        return;
      }

      await loadClassOptions();

      if (submoduleInitialized) {
        dynamicOptions[subClassOptionId] = [];
        resetSubclass();
      }

      submoduleInitialized = true;
    },
    { immediate: true },
  );

  watch(
    () => entity[classFieldId],
    async (newVal, oldVal) => {
      if (oldVal === newVal) return;

      if (
        submoduleInitialized &&
        oldVal !== undefined &&
        oldVal !== null &&
        newVal !== oldVal
      ) {
        resetSubclass();
      }

      await loadSubclassOptions();

      if (fetchFactorValuesOnChange) {
        await loadPowerFactor();
      }
    },
    { immediate: true },
  );

  watch(
    () => entity[subClassFieldId],
    async () => {
      if (fetchFactorValuesOnChange) {
        await loadPowerFactor();
      }
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
    resetSubclass,
  };
}
