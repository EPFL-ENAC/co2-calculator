<template>
  <div>
    <div class="planner-rf__header text-body2 text-grey-7">
      {{ $t('planner_rf_hint') }}
    </div>

    <q-separator />
    <div class="q-pa-md">
      <div class="text-weight-medium q-mb-sm">
        {{ $t('planner_budget_section_title') }}
      </div>
      <q-input
        v-model.number="budgetInput"
        class="planner-rf__budget"
        type="number"
        outlined
        dense
        hide-bottom-space
        min="0"
        :suffix="currencyLabel(budgetCurrency)"
        :label="
          $t('planner_submodule_budget_label', {
            submodule: $t(MODULES.ResearchFacilities),
          })
        "
        :loading="savingBudget"
        :disable="disable"
        @blur="saveBudget"
        @keyup.enter="saveBudget"
      />
      <div class="text-body2 text-grey-7 q-mt-sm">
        {{ $t('planner_submodule_budget_hint') }}
      </div>
    </div>

    <q-separator />
    <div class="q-pa-md">
      <q-select
        v-model="addModel"
        class="planner-rf__add"
        :options="filteredAddOptions"
        :label="$t('planner_rf_add_label')"
        outlined
        dense
        hide-bottom-space
        emit-value
        map-options
        use-input
        input-debounce="0"
        :disable="disable"
        @filter="filterAddOptions"
        @update:model-value="onAdd"
      >
        <template #prepend>
          <q-icon name="o_add_circle" color="info" />
        </template>
        <template #no-option>
          <q-item>
            <q-item-section class="text-grey-7">
              {{ $t('planner_rf_empty') }}
            </q-item-section>
          </q-item>
        </template>
      </q-select>
    </div>

    <template v-for="group in visibleGroups" :key="group.sub">
      <q-separator />
      <div class="planner-rf__group-header">
        <div class="text-h5 text-weight-medium">{{ $t(group.titleKey) }}</div>
      </div>
      <q-separator />

      <div class="planner-rf-table">
        <div
          v-for="row in selectedRowsOf(group.sub)"
          :key="row.key"
          class="planner-rf-table__row"
        >
          <div class="row items-center no-wrap">
            <label
              :for="`rf-${row.key}`"
              class="col text-body2 planner-rf-table__name"
            >
              {{ row.name }}
              <span v-if="row.facilityType" class="text-grey-7">
                ({{
                  $t(`${MODULES.ResearchFacilities}.type.${row.facilityType}`)
                }})
              </span>
            </label>
            <div class="planner-rf-table__kg text-body2 text-grey-7">
              <template v-if="row.kg !== null">
                {{ $t('planner_rf_kg_per_year', { value: formatKg(row.kg) }) }}
                <span v-if="projectYearsCount" class="text-weight-medium">
                  ·
                  {{
                    $t('planner_rf_kg_project', {
                      value: formatKg(row.kg * projectYearsCount),
                      years: projectYearsCount,
                    })
                  }}
                </span>
              </template>
            </div>
            <q-input
              :id="`rf-${row.key}`"
              v-model.number="row.use"
              class="planner-rf-table__input"
              type="number"
              outlined
              dense
              hide-bottom-space
              min="0"
              :suffix="row.metric"
              :aria-label="$t('planner_rf_use_label')"
              :disable="disable || savingKey === row.key"
              :loading="savingKey === row.key"
              @blur="save(row)"
              @keyup.enter="save(row)"
            />
            <q-btn
              flat
              dense
              round
              icon="o_delete"
              class="q-ml-sm"
              :disable="disable || savingKey === row.key"
              :aria-label="$t('common_delete')"
              @click="onRemove(row)"
            >
              <q-tooltip>{{ $t('common_delete') }}</q-tooltip>
            </q-btn>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

import { api } from 'src/api/http';
import { currencyLabel } from 'src/constant/currencies';
import {
  enumSubmodule,
  MODULES,
  SUBMODULE_RESEARCH_FACILITIES_TYPES,
} from 'src/constant/modules';
import { getModuleTypeId } from 'src/constant/moduleStates';
import { useSimulatorPlansStore } from 'src/stores/simulatorPlans';
import { useWorkspaceStore } from 'src/stores/workspace';

/**
 * Project Grant research-facilities grid (#1980): a dropdown offers the
 * reference year's whole platform list; picking one adds its row, where the
 * user enters the planned use in the platform's own metric (budget, hours,
 * CPU, housing, ...). Factors, and therefore the metric and the computed
 * kgCO₂eq, come from the reference year. A group (research facilities /
 * animal facilities) only renders once it holds a row.
 */

type RfSub = 'research-facilities' | 'animal_facilities';

interface RfRow {
  key: string;
  sub: RfSub;
  facilityId: string;
  name: string;
  /** Animal facilities only (rodent / fish). */
  facilityType: string | null;
  /** The platform's metric — the factor's use unit. */
  metric: string;
  selected: boolean;
  use: number | null;
  /** Last persisted use — `blur` after `Enter` must not save twice. */
  saved: number | null;
  entryId: number | null;
  kg: number | null;
}

interface RfFactor {
  researchfacility_id?: string | number;
  researchfacility_name?: string;
  researchfacility_type?: string;
  use_unit?: string;
}

interface RfEntry {
  id: number;
  researchfacility_id?: string | number;
  researchfacility_type?: string;
  use?: number | null;
  kg_co2eq?: number | null;
}

const props = defineProps<{
  carbonReportId: number;
  projectYearsCount?: number | null;
  grantBudgets?: Record<string, number> | null;
  budgetCurrency?: string | null;
  disable: boolean;
}>();

const $q = useQuasar();
const { t, n } = useI18n();
const plansStore = useSimulatorPlansStore();

const GROUPS: { sub: RfSub; titleKey: string }[] = [
  {
    sub: SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities,
    titleKey: 'planner_rf_common_title',
  },
  {
    sub: SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities,
    titleKey: `${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}`,
  },
];

const rows = ref<RfRow[]>([]);
const savingKey = ref<string | null>(null);

// A group appears once a platform of its kind is used, title and budget
// included; an empty group stays out of the way entirely.
const visibleGroups = computed(() =>
  GROUPS.filter((group) => selectedRowsOf(group.sub).length > 0),
);

// One budget for the whole module, stored under the module name — the same
// convention as the single-grid modules (#1978).
const BUDGET_KEY = MODULES.ResearchFacilities;
const budgetInput = ref<number | null>(
  props.grantBudgets?.[BUDGET_KEY] ?? null,
);
const savingBudget = ref(false);

function selectedRowsOf(sub: RfSub): RfRow[] {
  return rows.value.filter((row) => row.sub === sub && row.selected);
}

function optionLabel(row: RfRow): string {
  return row.facilityType
    ? `${row.name} (${t(`${MODULES.ResearchFacilities}.type.${row.facilityType}`)})`
    : row.name;
}

// The add dropdown offers every platform not yet used, filterable by name —
// the list holds ~90 platforms.
const addModel = ref<string | null>(null);
const addFilter = ref('');
const addOptions = computed(() =>
  rows.value
    .filter((row) => !row.selected)
    .map((row) => ({ label: optionLabel(row), value: row.key }))
    .sort((a, b) => a.label.localeCompare(b.label)),
);
const filteredAddOptions = computed(() => {
  const needle = addFilter.value.trim().toLowerCase();
  if (!needle) return addOptions.value;
  return addOptions.value.filter((opt) =>
    opt.label.toLowerCase().includes(needle),
  );
});

function filterAddOptions(input: string, update: (fn: () => void) => void) {
  update(() => {
    addFilter.value = input;
  });
}

function onAdd(key: string | null) {
  if (key === null) return;
  const row = rows.value.find((r) => r.key === key);
  if (row) row.selected = true;
  addModel.value = null;
}

async function onRemove(row: RfRow) {
  row.selected = false;
  row.use = null;
  await save(row);
}

function pathFor(sub: RfSub): string {
  return `carbon-reports/${props.carbonReportId}/modules/${MODULES.ResearchFacilities}/${sub}`;
}

/** Animal rows are one per (facility, type); common rows one per facility. */
function rowKey(sub: RfSub, facilityId: string, facilityType: string | null) {
  return `${sub}:${facilityId}${facilityType ? `:${facilityType}` : ''}`;
}

// The platform list follows the current workspace year — the year whose
// Calculator holds the platforms as the user knows them.
const workspaceYear = useWorkspaceStore().selectedYear;

async function fetchFactors(sub: RfSub): Promise<RfFactor[]> {
  if (workspaceYear === null) return [];
  return api
    .get(`factors/${enumSubmodule[sub]}/list?year=${workspaceYear}`)
    .json<RfFactor[]>();
}

async function fetchEntries(sub: RfSub): Promise<RfEntry[]> {
  try {
    const res = await api
      .get(`${pathFor(sub)}?page=1&limit=200`)
      .json<{ items: RfEntry[] }>();
    return res.items;
  } catch {
    // Empty module → no rows yet; every platform stays unselected.
    return [];
  }
}

function bindEntries(sub: RfSub, entries: RfEntry[]) {
  const byKey = new Map(
    entries.map((entry) => [
      rowKey(
        sub,
        String(entry.researchfacility_id ?? ''),
        entry.researchfacility_type ?? null,
      ),
      entry,
    ]),
  );
  for (const row of rows.value) {
    if (row.sub !== sub) continue;
    const entry = byKey.get(row.key);
    row.entryId = entry?.id ?? null;
    row.kg = entry?.kg_co2eq ?? null;
    row.use = entry?.use ?? row.use;
    row.saved = entry?.use ?? null;
    if (entry) row.selected = true;
  }
}

async function loadGroup(sub: RfSub) {
  const [factors, entries] = await Promise.all([
    fetchFactors(sub),
    fetchEntries(sub),
  ]);
  const groupRows: RfRow[] = factors
    .filter((f) => f.researchfacility_name && f.use_unit)
    .map((f) => ({
      key: rowKey(
        sub,
        String(f.researchfacility_id ?? ''),
        f.researchfacility_type ?? null,
      ),
      sub,
      facilityId: String(f.researchfacility_id ?? ''),
      name: f.researchfacility_name as string,
      facilityType: f.researchfacility_type ?? null,
      metric: f.use_unit as string,
      selected: false,
      use: null,
      saved: null,
      entryId: null,
      kg: null,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
  rows.value = [...rows.value.filter((row) => row.sub !== sub), ...groupRows];
  bindEntries(sub, entries);
}

function formatKg(value: number): string {
  return n(Math.round(value));
}

/** Saves run one after another — see PlannerPurchaseRows for the rationale. */
let saveQueue: Promise<void> = Promise.resolve();

function save(row: RfRow): Promise<void> {
  saveQueue = saveQueue.then(() => persist(row));
  return saveQueue;
}

async function persist(row: RfRow) {
  const use =
    typeof row.use === 'number' && Number.isFinite(row.use) && row.use >= 0
      ? row.use
      : null;
  if (use === row.saved) return;
  savingKey.value = row.key;
  try {
    if (use === null) {
      if (row.entryId !== null) {
        await api.delete(`${pathFor(row.sub)}/${row.entryId}`);
        row.entryId = null;
        row.kg = null;
      }
    } else if (row.entryId === null) {
      await api.post(pathFor(row.sub), { json: createPayload(row, use) });
    } else {
      await api.patch(`${pathFor(row.sub)}/${row.entryId}`, {
        json: { use },
      });
    }
    row.saved = use;
    bindEntries(row.sub, await fetchEntries(row.sub));
    await plansStore.refreshAggregateIfActive();
  } catch {
    $q.notify({ type: 'negative', message: t('planner_rf_save_error') });
  } finally {
    savingKey.value = null;
  }
}

function createPayload(row: RfRow, use: number): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    researchfacility_id: row.facilityId,
    researchfacility_name: row.name,
    use,
    use_unit: row.metric,
  };
  if (row.facilityType) payload.researchfacility_type = row.facilityType;
  return payload;
}

async function saveBudget() {
  const raw = budgetInput.value;
  const value =
    typeof raw === 'number' && Number.isFinite(raw) && raw >= 0 ? raw : null;
  if (value === (props.grantBudgets?.[BUDGET_KEY] ?? null)) return;
  savingBudget.value = true;
  try {
    await plansStore.setSubmoduleBudget(
      props.carbonReportId,
      getModuleTypeId(MODULES.ResearchFacilities),
      BUDGET_KEY,
      value,
    );
  } catch {
    $q.notify({ type: 'negative', message: t('planner_grant_budget_error') });
  } finally {
    savingBudget.value = false;
  }
}

onMounted(async () => {
  await Promise.all(GROUPS.map((group) => loadGroup(group.sub)));
});
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.planner-rf__header {
  padding: tokens.$spacing-md;
}

.planner-rf__add {
  max-width: 420px;

  // Quasar gives field marginals a fixed height taller than the dense
  // control, which floats the icon high; center the marginal in the row
  // instead.
  :deep(.q-field__prepend) {
    height: auto;
    align-self: center;
  }
}

.planner-rf__group-header {
  padding: tokens.$spacing-md;
}

.planner-rf__budget {
  max-width: 240px;
}

.planner-rf-table {
  &__row {
    padding: tokens.$spacing-xs tokens.$spacing-md;
    background-color: tokens.$table-bg-odd;

    &:nth-child(even) {
      background-color: tokens.$table-bg-even;
    }
  }

  &__kg {
    padding-right: tokens.$spacing-lg;
  }

  &__input {
    width: tokens.$planner-grid-amount-input-width;

    :deep(.q-field__control) {
      background-color: tokens.$table-bg-odd;
    }

    :deep(.q-field__suffix) {
      font-size: tokens.$text-size-sm;
      color: tokens.$color-text-muted;
    }
  }
}
</style>
