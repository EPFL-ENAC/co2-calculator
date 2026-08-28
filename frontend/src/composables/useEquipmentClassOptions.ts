import { ref, shallowReactive, watch, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useFactorsStore } from '@/stores/factors';
import { AllSubmoduleTypes } from '@/constant/modules';

type Option = { label: string; value: string };

interface FieldConfig {
  // identifiers of the fields in the entity record (real value we want to use)
  classFieldId?: string;
  subClassFieldId?: string;
  // Set when the class value itself is an opaque code (research facility ids):
  // the select then shows the taxonomy node's server-side label instead of the
  // stored value (#2007). Which factor field backs that label is the module
  // handler's `kind_label_field`, not the frontend's business.
  classLabelField?: string;
  // identifiers of the power fields in the entity record
  // (where to write the fetched power values)
  classOptionId?: string;
  subClassOptionId?: string;
  // entity fields always overwritten with the fetched factor values; each id
  // must match the key in the factor response (e.g. "active_power_w").
  // Use for read-only fields that should mirror the factor.
  valueFieldIds?: string[];
  // entity fields filled from the factor only when currently empty, so a user's
  // saved/edited value is preserved (e.g. "active_usage_hours_per_week").
  defaultValueFieldIds?: string[];

  // Whether to automatically fetch power factor values when class/subclass changes.
  // Default is false to avoid unexpected API calls and allow the user to explicitly
  //  trigger fetch (for example with a button), but can be enabled if desired.
  // case where it might be desirable to set this to true: when the form
  // is primarily for data viewing rather than editing, so automatic fetching on change would be more intuitive and efficient.
  // ALSO: table row where class/subclass are  editable shoudl have this
  // flag as false: because -> if user is editing class/subclass in
  // a table row, they might not want to trigger power factor fetch
  // until they have finished editing both class and subclass, and automatic fetching on change could lead to multiple unnecessary API calls and potentially inconsistent intermediate states.
  fetchFactorValuesOnChange?: boolean;
}

export function useEquipmentClassOptions<
  TEntity extends Record<string, unknown>,
>(
  entity: TEntity,
  moduleType: Ref<string>,
  submoduleType: Ref<AllSubmoduleTypes>,
  config: FieldConfig = {},
  year?: Ref<string | number | null | undefined>,
) {
  const { t, te } = useI18n();

  const classFieldId = config.classFieldId ?? '';
  const subClassFieldId = config.subClassFieldId ?? '';

  const classOptionId = config.classOptionId ?? 'kind';
  const subClassOptionId = config.subClassOptionId ?? 'subkind';
  const valueFieldIds = config.valueFieldIds ?? [];
  const defaultValueFieldIds = config.defaultValueFieldIds ?? [];

  const fetchFactorValuesOnChange: boolean =
    config.fetchFactorValuesOnChange ?? false;

  const dynamicOptions = shallowReactive<Record<string, Option[]>>({});
  const loadingClasses = ref(false);
  const loadingSubclasses = ref(false);
  const loadingPowerFactor = ref(false);
  const classLoadError = ref(false);
  const subclassLoadError = ref(false);

  const store = useFactorsStore();

  function isEmpty(raw: unknown): boolean {
    return raw === null || raw === undefined || raw === '';
  }

  function normalizeValue(raw: unknown): string | null {
    if (raw === null || raw === undefined || raw === '') return null;
    if (typeof raw === 'object' && 'value' in (raw as Option)) {
      return String((raw as Option).value);
    }
    return String(raw);
  }

  async function loadClassOptions() {
    const sub = submoduleType.value;
    // `year` is required by the taxonomy endpoint (factors are year-scoped);
    // without it the request 422s.
    const yearValue = year?.value;
    if (!sub || yearValue == null) return;
    loadingClasses.value = true;
    classLoadError.value = false;
    try {
      const rawClasses = await store.fetchClassOptions(
        moduleType.value,
        sub,
        yearValue,
        Boolean(config.classLabelField),
      );
      dynamicOptions[classOptionId] = rawClasses.map((o) => ({
        label: te(o.label) ? t(o.label) : o.label,
        value: o.value,
      }));
    } catch {
      // #2498: an empty list here is otherwise indistinguishable from "this
      // submodule genuinely has no classes" — the select would silently show
      // nothing instead of surfacing that the lookup itself failed.
      dynamicOptions[classOptionId] = [];
      classLoadError.value = true;
    } finally {
      loadingClasses.value = false;
    }
  }

  async function loadSubclassOptions() {
    const sub = submoduleType.value;
    const cls = normalizeValue(entity[classFieldId]);
    const yearValue = year?.value;
    if (!sub || !cls || yearValue == null) {
      dynamicOptions[subClassOptionId] = [];
      subclassLoadError.value = false;
      return;
    }
    loadingSubclasses.value = true;
    subclassLoadError.value = false;
    try {
      const rawOptions = await store.fetchSubclassOptions(
        moduleType.value,
        sub,
        cls,
        yearValue,
      );
      const options = rawOptions.map((o) => ({
        label: te(o.label) ? t(o.label) : o.label,
        value: o.value,
      }));
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

    const yearValue = year?.value;
    if (yearValue == null) return;

    loadingPowerFactor.value = true;
    try {
      const pf = await store.fetchPowerFactor(sub, cls, subCls, yearValue);
      if (pf) {
        valueFieldIds.forEach((fieldId) => {
          if (fieldId && fieldId in entity)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (entity as any)[fieldId] = pf[fieldId] ?? null;
        });
        // Only seed default fields that have no value yet, so an existing
        // user-entered value is never overwritten.
        defaultValueFieldIds.forEach((fieldId) => {
          if (fieldId && fieldId in entity && isEmpty(entity[fieldId]))
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (entity as any)[fieldId] = pf[fieldId] ?? null;
        });
      }
    } catch {
      // ignore, user can still fill manually
      // should set error though
    } finally {
      loadingPowerFactor.value = false;
    }
  }

  function resetSubclass() {
    if (subClassFieldId in entity)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (entity as any)[subClassFieldId] = '';
    // Clear both always-overwritten and default fields so an explicit
    // class/subclass change re-seeds them from the new factor.
    [...valueFieldIds, ...defaultValueFieldIds].forEach((fieldId) => {
      if (fieldId in entity)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (entity as any)[fieldId] = null;
    });
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

      if (fetchFactorValuesOnChange) {
        await loadPowerFactor();
      }
    },
    { immediate: true },
  );

  // When subclass changes, refresh power factor
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
    classLoadError,
    subclassLoadError,
    loadClassOptions,
    loadSubclassOptions,
    loadPowerFactor,
    resetSubclass,
  };
}
