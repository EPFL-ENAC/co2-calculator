import { reactive, ref, watch, type Ref } from 'vue';
import { useFactorsStore } from 'src/stores/factors';
import type { AllSubmoduleTypes } from 'src/constant/modules';

type Option = { label: string; value: string };

export interface TreeLevelConfig {
  fieldId: string;
  optionKey: string;
}

export interface TreeConfig {
  levels: TreeLevelConfig[];
  /** Called when the deepest populated level changes (for power-factor side-effects). */
  onLeafChange?: (selections: (string | null)[]) => void;
}

export function useClassificationTree<TEntity extends Record<string, unknown>>(
  entity: TEntity,
  submoduleType: Ref<AllSubmoduleTypes>,
  config: TreeConfig,
) {
  const { levels, onLeafChange } = config;
  const store = useFactorsStore();

  const dynamicOptions = reactive<Record<string, Option[]>>({});
  const loading = ref(false);

  function normalizeValue(raw: unknown): string | null {
    if (raw === null || raw === undefined || raw === '') return null;
    if (typeof raw === 'object' && raw !== null && 'value' in raw) {
      return String((raw as { value: unknown }).value);
    }
    return String(raw);
  }

  function getSelections(upToLevel: number): string[] {
    const path: string[] = [];
    for (let i = 0; i < upToLevel && i < levels.length; i++) {
      const val = normalizeValue(entity[levels[i].fieldId]);
      if (!val) break;
      path.push(val);
    }
    return path;
  }

  function refreshOptionsForLevel(levelIndex: number) {
    if (levelIndex < 0 || levelIndex >= levels.length) return;
    const path = getSelections(levelIndex);
    dynamicOptions[levels[levelIndex].optionKey] = store.getOptionsAtPath(
      submoduleType.value,
      path,
    );
  }

  function resetLevelsFrom(startLevel: number) {
    for (let i = startLevel; i < levels.length; i++) {
      dynamicOptions[levels[i].optionKey] = [];
      if (levels[i].fieldId in entity) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (entity as any)[levels[i].fieldId] = '';
      }
    }
  }

  let initialized = false;

  watch(
    submoduleType,
    async () => {
      if (!submoduleType.value) {
        for (const lvl of levels) {
          dynamicOptions[lvl.optionKey] = [];
        }
        return;
      }

      loading.value = true;
      try {
        await store.ensureTree(submoduleType.value);
      } catch {
        // tree fetch failed
      } finally {
        loading.value = false;
      }

      refreshOptionsForLevel(0);

      if (initialized) {
        resetLevelsFrom(1);
      } else {
        // First load: refresh child levels that already have a parent value
        // (e.g. when editing an existing row whose entity is pre-populated)
        for (let i = 1; i < levels.length; i++) {
          const parentVal = normalizeValue(entity[levels[i - 1].fieldId]);
          if (parentVal) {
            refreshOptionsForLevel(i);
          }
        }
      }

      initialized = true;
    },
    { immediate: true },
  );

  levels.forEach((lvl, idx) => {
    watch(
      () => entity[lvl.fieldId],
      (newVal, oldVal) => {
        if (oldVal === newVal) return;

        if (initialized && oldVal !== undefined && oldVal !== null) {
          resetLevelsFrom(idx + 1);
        }

        if (idx + 1 < levels.length) {
          refreshOptionsForLevel(idx + 1);
        }

        if (onLeafChange) {
          onLeafChange(levels.map((l) => normalizeValue(entity[l.fieldId])));
        }
      },
      { immediate: idx === 0 },
    );
  });

  /**
   * For a given optionKey, return the corresponding level index (-1 if not found).
   */
  function levelIndexOf(optionKey: string): number {
    return levels.findIndex((l) => l.optionKey === optionKey);
  }

  /**
   * Whether the level should show a placeholder (parent not yet selected).
   */
  function isPlaceholder(optionKey: string): boolean {
    const idx = levelIndexOf(optionKey);
    if (idx <= 0) return false;
    const parentVal = normalizeValue(entity[levels[idx - 1].fieldId]);
    return !parentVal;
  }

  /**
   * Whether the level is currently loading (only true during initial tree fetch).
   */
  function isLevelLoading(optionKey: string): boolean {
    const idx = levelIndexOf(optionKey);
    if (idx === 0) return loading.value;
    if (idx > 0) {
      const parentVal = normalizeValue(entity[levels[idx - 1].fieldId]);
      return loading.value && !!parentVal;
    }
    return false;
  }

  return {
    dynamicOptions,
    loading,
    levelIndexOf,
    isPlaceholder,
    isLevelLoading,
  };
}
