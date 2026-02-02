import { reactive, ref, watch, type Ref } from 'vue';
import { useFactorsStore } from 'src/stores/powerFactors';
import { AllSubmoduleTypes } from 'src/constant/modules';

type Option = { label: string; value: string };

interface FieldConfig {
  // identifiers of the fields in the entity record (real value we want to use)
  classFieldId?: string;
  subClassFieldId?: string;
  // identifiers of the power fields in the entity record
  // (where to write the fetched power values)
  classOptionId?: string;
  subClassOptionId?: string;
  // values of the fields in the entity record (real value we want to use)
  actPowerFieldId?: string;
  pasPowerFieldId?: string;
}

export function useEquipmentClassOptions<
  TEntity extends Record<string, unknown>,
>(
  entity: TEntity,
  submoduleType: Ref<AllSubmoduleTypes>,
  config: FieldConfig = {},
) {
  const classFieldId = config.classFieldId ?? '';
  const subClassFieldId = config.subClassFieldId ?? '';

  const classOptionId = config.classOptionId ?? 'kind';
  const subClassOptionId = config.subClassOptionId ?? 'subkind';
  // #  TODO: make power field IDs configurable
  const actPowerFieldId = config.actPowerFieldId ?? 'act_power';
  const pasPowerFieldId = config.pasPowerFieldId ?? 'pas_power';

  console.log(
    'Using classFieldId:',
    classFieldId,
    'subClassFieldId:',
    subClassFieldId,
  );

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
    // If subclass options exist and are non-empty, then a subclass is required
    const options = dynamicOptions[subClassOptionId];
    return Array.isArray(options) && options.length > 0;
  }

  async function loadPowerFactor() {
    const sub = submoduleType.value;
    if (!sub) return;

    const cls = normalizeValue(entity[classFieldId]);
    if (!cls) return;

    const subCls = normalizeValue(entity[subClassFieldId]);
    // Only load power factor if:
    // 1. Subclass is NOT required (no subclass options available), OR
    // 2. Subclass is required AND one has been selected
    if (subclassRequired() && !subCls) {
      // Subclass is required but not selected yet - don't fetch power factor
      return;
    }

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

  function resetSubclass() {
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
      // maybe oldVal is undefined on first run, but we only want to
      // reset subclass if the class actually changed.
      console.log(
        'Class changed from',
        oldVal,
        'to',
        newVal,
        entity,
        classFieldId,
      );
      if (oldVal === newVal) {
        return;
      }

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

      await loadSubclassOptions();

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
    resetSubclass,
  };
}
