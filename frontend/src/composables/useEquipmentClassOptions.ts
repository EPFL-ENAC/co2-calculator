import { reactive, ref, watch, type Ref } from 'vue';
import { usePowerFactorsStore } from 'src/stores/powerFactors';

type Option = { label: string; value: string };

type SubmoduleType = 'scientific' | 'it' | 'other' | undefined;

interface FieldConfig {
  classFieldId?: string;
  subClassFieldId?: string;
}

export function useEquipmentClassOptions<
  TEntity extends Record<string, unknown>,
>(
  entity: TEntity,
  submoduleType: Ref<SubmoduleType>,
  config: FieldConfig = {},
) {
  const classFieldId = config.classFieldId ?? 'class';
  const subClassFieldId = config.subClassFieldId ?? 'sub_class';

  const dynamicOptions = reactive<Record<string, Option[]>>({});
  const loadingClasses = ref(false);
  const loadingSubclasses = ref(false);
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

  function resetSubclass() {
    if (subClassFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[subClassFieldId] = '';
  }

  // React to submodule type changes
  let submoduleInitialized = false;
  watch(
    submoduleType,
    async () => {
      if (!submoduleType.value) {
        dynamicOptions[classFieldId] = [];
        dynamicOptions[subClassFieldId] = [];
        resetSubclass();
        return;
      }

      await loadClassOptions();

      // On first initialization, keep existing subclass values so
      // editing an existing row doesn't lose data. On subsequent
      // submodule changes, clear subclass field.
      if (submoduleInitialized) {
        dynamicOptions[subClassFieldId] = [];
        resetSubclass();
      }

      submoduleInitialized = true;
    },
    { immediate: true },
  );

  // When class changes, refresh subclasses
  watch(
    () => entity[classFieldId],
    async (newVal, oldVal) => {
      await loadSubclassOptions();

      // If the class has changed after initialization, clear
      // subclass so the user explicitly re-selects.
      if (
        submoduleInitialized &&
        oldVal !== undefined &&
        oldVal !== null &&
        newVal !== oldVal
      ) {
        resetSubclass();
      }
    },
    { immediate: true },
  );

  return {
    dynamicOptions,
    loadingClasses,
    loadingSubclasses,
    subclassLoadError,
    loadClassOptions,
    loadSubclassOptions,
    resetSubclass,
  };
}
