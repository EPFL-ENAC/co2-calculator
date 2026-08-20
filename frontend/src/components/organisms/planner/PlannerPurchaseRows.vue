<template>
  <div>
    <!-- The backend accepts a global budget XOR per-category totals (PRD
         #1555), so the two modes are one explicit choice rather than two
         tables the user discovers are incompatible. -->
    <div class="planner-purchase__header row items-center justify-between">
      <div>
        <div class="planner-purchase-mode row items-center no-wrap">
          <button
            type="button"
            class="planner-purchase-mode__label text-body1"
            :class="mode === 'global' ? 'text-weight-medium' : 'text-grey-6'"
            :disabled="disable || switching"
            :aria-pressed="mode === 'global'"
            @click="onModeRequest('global')"
          >
            {{ $t('planner_purchase_mode_global') }}
          </button>
          <q-toggle
            :model-value="mode === 'per_category'"
            color="info"
            keep-color
            size="lg"
            :disable="disable || switching"
            @update:model-value="
              (on: boolean) => onModeRequest(on ? 'per_category' : 'global')
            "
          />
          <button
            type="button"
            class="planner-purchase-mode__label text-body1"
            :class="
              mode === 'per_category' ? 'text-weight-medium' : 'text-grey-6'
            "
            :disabled="disable || switching"
            :aria-pressed="mode === 'per_category'"
            @click="onModeRequest('per_category')"
          >
            {{ $t('planner_purchase_mode_per_category') }}
          </button>
        </div>
        <div class="text-body2 text-grey-7">
          {{ $t('planner_purchase_mode_hint') }}
        </div>
      </div>
      <q-select
        :model-value="currency"
        :options="CURRENCY_OPTIONS"
        emit-value
        map-options
        outlined
        dense
        options-dense
        class="planner-purchase__currency"
        :label="$t('planner_budget_currency_label')"
        :disable="disable || switching || savingKey !== null"
        @update:model-value="onCurrencyChange"
      />
    </div>

    <q-separator />

    <!-- Reads as a table, like the headcount grid: full-width striped rows
         carry the eye from the category across to its field. -->
    <div class="planner-purchase-table">
      <div
        v-for="row in visibleRows"
        :key="row.key"
        class="planner-purchase-table__row"
      >
        <div class="row items-center no-wrap">
          <label :for="`purchase-${row.key}`" class="col text-body2">
            {{ $t(row.labelKey) }}
          </label>
          <div class="planner-purchase-table__kg text-body2 text-grey-7">
            <template v-if="row.kg !== null">
              <template v-if="projectYearsCount != null">
                {{
                  $t('planner_purchase_kg_per_year', {
                    value: formatTonnesCO2(row.kg / 1000),
                  })
                }}
                <span class="text-weight-medium q-ml-sm">
                  {{
                    $t('planner_purchase_kg_project', {
                      value: formatTonnesCO2(
                        (row.kg * projectYearsCount) / 1000,
                      ),
                      years: projectYearsCount,
                    })
                  }}
                </span>
              </template>
              <template v-else>
                {{ formatTonnesCO2(row.kg / 1000) }} {{ $t('tco2eq') }}
              </template>
            </template>
          </div>
          <q-input
            :id="`purchase-${row.key}`"
            v-model.number="row.amount"
            class="planner-purchase-table__input"
            type="number"
            outlined
            dense
            hide-bottom-space
            min="0"
            :suffix="currencyLabel(currency)"
            :aria-label="$t('planner_purchase_amount_label')"
            :disable="disable || switching || savingKey === row.key"
            :loading="savingKey === row.key"
            :error="row.error !== null"
            @blur="save(row)"
            @keyup.enter="save(row)"
          />
        </div>
        <!-- Full width: the rule that was broken needs a sentence, which does
             not fit under the field. -->
        <div v-if="row.error" class="text-body2 text-negative q-mt-xs">
          {{ row.error }}
        </div>
      </div>
    </div>

    <q-dialog v-model="confirmOpen" :persistent="switching">
      <q-card style="min-width: 420px">
        <q-card-section class="text-h4 text-weight-medium">
          {{ $t('planner_purchase_switch_dialog_title') }}
        </q-card-section>
        <q-card-section class="text-body2 text-grey-8 q-pt-none">
          {{ $t(switchDialogMessageKey) }}
        </q-card-section>
        <q-card-actions class="q-px-md q-pb-md">
          <q-btn
            :label="$t('common_validate_short')"
            :loading="switching"
            color="info"
            unelevated
            no-caps
            class="text-weight-medium"
            @click="confirmSwitch"
          />
          <q-btn
            v-close-popup
            :label="$t('common_cancel')"
            :disable="switching"
            color="primary"
            unelevated
            outline
            no-caps
            class="text-weight-medium"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

import { api } from 'src/api/http';
import { CURRENCY_OPTIONS, currencyLabel } from 'src/constant/currencies';
import { useSimulatorPlansStore } from 'src/stores/simulatorPlans';
import { formatTonnesCO2 } from 'src/utils/number';

// The 8 backend categories (modules_planner/purchase/emissions.py
// PLANNER_PURCHASE_EMISSIONS), rendered as fixed rows in the design's order.
const CATEGORIES = [
  'scientific_equipment',
  'it_equipment',
  'consumable_accessories',
  'biological_chemical_gaseous_product',
  'services',
  'vehicles',
  'other_purchases',
  'purchases_centralized',
] as const;

type Mode = 'global' | 'per_category';

const SUBMODULE: Record<Mode, string> = {
  global: 'planner_purchase_budget',
  per_category: 'planner_purchase',
};

// The XOR and duplicate-category rules are 422 `detail` codes raised by
// CarbonReportModuleWorkflow._check_planner_purchase_exclusivity. The mode
// toggle prevents them, but a second tab can still lose the race.
const ERROR_MESSAGE_KEYS: Record<string, string> = {
  PURCHASES_GLOBAL_BUDGET_SET: 'planner_purchase_error_global_budget_set',
  PURCHASES_SUBMODULE_TOTALS_SET: 'planner_purchase_error_totals_set',
  PURCHASES_GLOBAL_BUDGET_EXISTS: 'planner_purchase_error_budget_exists',
  DUPLICATE_PURCHASE_CATEGORY: 'planner_purchase_error_duplicate_category',
};

interface PurchaseRow {
  key: string;
  labelKey: string;
  /** The category slug sent on create; null for the global budget. */
  category: string | null;
  amount: number | null;
  /** Last persisted amount — `blur` after `Enter` must not save twice. */
  saved: number | null;
  entryId: number | null;
  kg: number | null;
  error: string | null;
}

interface SubmoduleItem {
  id: number;
  purchase_category?: string;
  amount_eur?: number | null;
  kg_co2eq?: number | null;
}

const props = defineProps<{
  carbonReportId: number;
  disable: boolean;
  /** Set in the Project Grant section: multiply kg over the plan's years. */
  projectYearsCount?: number | null;
  /** Grant plans carry a budget currency; it seeds the selector. */
  budgetCurrency?: string | null;
  /** The year whose average ECB rate converts amounts, matching the backend. */
  factorYear?: number | null;
}>();

const $q = useQuasar();
const { t } = useI18n();
const plansStore = useSimulatorPlansStore();

const mode = ref<Mode>('global');
// Amounts are stored in EUR; the selected currency only denominates what the
// user types and sees. `eurPerUnit` converts both ways at the factor year's
// average rate — the same rate the backend applies on write.
const currency = ref<string>('eur');
const eurPerUnit = ref<number>(1);
let ratesByCode: Record<string, number> | null = null;
const savingKey = ref<string | null>(null);
const switching = ref(false);
const confirmOpen = ref(false);
const pendingMode = ref<Mode | null>(null);

const budgetRow = ref<PurchaseRow>(emptyRow('global'));
const categoryRows = ref<PurchaseRow[]>(
  CATEGORIES.map((category) => emptyRow(category)),
);

const visibleRows = computed(() => rowsFor(mode.value));

const switchDialogMessageKey = computed(() =>
  mode.value === 'global'
    ? 'planner_purchase_switch_from_global_message'
    : 'planner_purchase_switch_from_categories_message',
);

function emptyRow(key: string): PurchaseRow {
  return {
    key,
    labelKey:
      key === 'global'
        ? 'planner_purchase_global_budget_label'
        : `planner_purchase_category.${key}`,
    category: key === 'global' ? null : key,
    amount: null,
    saved: null,
    entryId: null,
    kg: null,
    error: null,
  };
}

function rowsFor(target: Mode): PurchaseRow[] {
  return target === 'global' ? [budgetRow.value] : categoryRows.value;
}

function pathFor(target: Mode): string {
  return `carbon-reports/${props.carbonReportId}/modules/purchase/${SUBMODULE[target]}`;
}

async function fetchItems(target: Mode): Promise<SubmoduleItem[]> {
  try {
    const res = await api
      .get(`${pathFor(target)}?page=1&limit=100`)
      .json<{ items: SubmoduleItem[] }>();
    return res.items;
  } catch {
    // Empty module → no rows yet; leave the blank inputs.
    return [];
  }
}

async function rateFor(code: string): Promise<number | null> {
  if (code === 'eur') return 1;
  if (props.factorYear == null) return null;
  if (ratesByCode === null) {
    try {
      ratesByCode = await api
        .get(`exchange-rates/${props.factorYear}`, { skipErrorCodes: [404] })
        .json<Record<string, number>>();
    } catch {
      return null;
    }
  }
  return ratesByCode[code] ?? null;
}

function toDisplay(amountEur: number | null | undefined): number | null {
  if (amountEur == null) return null;
  return Math.round((amountEur / eurPerUnit.value) * 100) / 100;
}

function fillRow(row: PurchaseRow, item: SubmoduleItem | undefined) {
  row.amount = toDisplay(item?.amount_eur);
  row.saved = row.amount;
  row.entryId = item?.id ?? null;
  // A saved amount always reads a figure: a category the reference year has no
  // factor for is 0, not blank.
  row.kg = item ? (item.kg_co2eq ?? 0) : null;
  row.error = null;
}

async function load() {
  const [totals, budgets] = await Promise.all([
    fetchItems('per_category'),
    fetchItems('global'),
  ]);
  const byCategory = new Map(
    totals
      .filter((it) => it.purchase_category)
      .map((it) => [it.purchase_category as string, it]),
  );
  categoryRows.value.forEach((row) => fillRow(row, byCategory.get(row.key)));
  fillRow(budgetRow.value, budgets[0]);
  // The mode the data is already in wins; an untouched module opens on the
  // single-field path.
  mode.value = budgets.length
    ? 'global'
    : totals.length
      ? 'per_category'
      : 'global';
}

/** Re-read the emissions of the saved kind without touching typed amounts. */
async function refreshKg() {
  const items = await fetchItems(mode.value);
  const byId = new Map(items.map((it) => [it.id, it.kg_co2eq ?? 0]));
  rowsFor(mode.value).forEach((row) => {
    row.kg = row.entryId === null ? null : (byId.get(row.entryId) ?? 0);
  });
}

async function errorDetail(error: unknown): Promise<string | null> {
  if (!error || typeof error !== 'object' || !('response' in error))
    return null;
  try {
    const body = await (error as { response: Response }).response
      .clone()
      .json();
    return typeof body?.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}

function statusOf(error: unknown): number | null {
  if (!error || typeof error !== 'object' || !('response' in error))
    return null;
  return (error as { response: Response }).response.status ?? null;
}

/**
 * Saves run one after another: `Enter` then `blur` fire on the same edit, and
 * concurrently they would each see "no entry yet" and create a duplicate.
 * Queueing (rather than dropping) also keeps a second row's edit, made while
 * the first is still in flight.
 */
let saveQueue: Promise<void> = Promise.resolve();

function save(row: PurchaseRow): Promise<void> {
  saveQueue = saveQueue.then(() => persist(row));
  return saveQueue;
}

async function persist(row: PurchaseRow) {
  const amount =
    typeof row.amount === 'number' && Number.isFinite(row.amount)
      ? row.amount
      : null;
  // Re-checked here, not when queued: the duplicate call runs after the first
  // one has recorded what it persisted.
  if (amount === row.saved) return;
  row.error = null;
  savingKey.value = row.key;
  try {
    if (amount === null) {
      // Clearing the field deletes the entry — that is also how a mode with
      // one leftover value stops blocking the other one.
      await api.delete(`${pathFor(mode.value)}/${row.entryId}`, {
        skipErrorCodes: [422],
      });
      row.entryId = null;
      row.kg = null;
    } else if (row.entryId === null) {
      const created = await api
        .post(pathFor(mode.value), {
          json: row.category
            ? {
                purchase_category: row.category,
                amount_eur: amount,
                currency: currency.value,
              }
            : { amount_eur: amount, currency: currency.value },
          skipErrorCodes: [422],
        })
        .json<{ id: number }>();
      row.entryId = created.id;
    } else {
      await api
        .patch(`${pathFor(mode.value)}/${row.entryId}`, {
          json: { amount_eur: amount, currency: currency.value },
          skipErrorCodes: [422],
        })
        .json();
    }
    row.saved = amount;
    await refreshKg();
    await plansStore.refreshAggregateIfActive();
  } catch (error: unknown) {
    // 422 is the business rule and belongs on the field; anything else has
    // already been surfaced by the http hook.
    if (statusOf(error) !== 422) return;
    const detail = await errorDetail(error);
    const messageKey = detail ? ERROR_MESSAGE_KEYS[detail] : undefined;
    row.error = messageKey ? t(messageKey) : t('planner_purchase_save_error');
  } finally {
    savingKey.value = null;
  }
}

function filledRows(target: Mode): PurchaseRow[] {
  return rowsFor(target).filter((row) => row.entryId !== null);
}

async function seedCurrency() {
  const seeded = (props.budgetCurrency || 'eur').toLowerCase();
  if (seeded === 'eur') return;
  const rate = await rateFor(seeded);
  if (rate === null) return;
  currency.value = seeded;
  eurPerUnit.value = rate;
}

async function onCurrencyChange(next: string) {
  if (next === currency.value) return;
  const rate = await rateFor(next);
  if (rate === null) {
    $q.notify({
      type: 'negative',
      message: t('planner_currency_rates_unavailable'),
    });
    return;
  }
  // A pending blur-save must land before the rows are re-read and converted.
  await saveQueue;
  currency.value = next;
  eurPerUnit.value = rate;
  await load();
}

function onModeRequest(next: Mode) {
  if (next === mode.value) return;
  // The backend refuses both kinds at once, so switching means dropping what
  // the current mode holds — never silently.
  if (filledRows(mode.value).length > 0) {
    pendingMode.value = next;
    confirmOpen.value = true;
    return;
  }
  mode.value = next;
}

async function confirmSwitch() {
  const next = pendingMode.value;
  if (next === null) return;
  const previous = mode.value;
  switching.value = true;
  try {
    // A pending blur-save would otherwise re-create what we are deleting.
    await saveQueue;
    // Read the server rather than the rows: another tab may have added an
    // entry this component never bound, and one leftover blocks the mode
    // being switched to.
    for (const item of await fetchItems(previous)) {
      await api.delete(`${pathFor(previous)}/${item.id}`);
    }
    rowsFor(previous).forEach((row) => fillRow(row, undefined));
    mode.value = next;
    pendingMode.value = null;
    confirmOpen.value = false;
    await plansStore.refreshAggregateIfActive();
  } catch {
    $q.notify({ type: 'negative', message: t('planner_purchase_save_error') });
  } finally {
    switching.value = false;
  }
}

onMounted(async () => {
  await seedCurrency();
  await load();
});
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

// The stripes run edge to edge, so only the mode choice above them is inset.
.planner-purchase__header {
  padding: tokens.$spacing-md;
}

.planner-purchase__currency {
  width: tokens.$planner-grid-amount-input-width;
}

.planner-purchase-table {
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

    // The field keeps its own white surface so it stays legible on the
    // shaded stripes instead of picking up the row behind it.
    :deep(.q-field__control) {
      background-color: tokens.$table-bg-odd;
    }

    // The currency is a unit, not part of the value the user typed.
    :deep(.q-field__suffix) {
      font-size: tokens.$text-size-sm;
      color: tokens.$color-text-muted;
    }
  }
}

// Both modes are named on either side of the switch; the one not in use reads
// as unavailable rather than disappearing.
.planner-purchase-mode__label {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  cursor: pointer;

  &:disabled {
    cursor: default;
  }
}
</style>
