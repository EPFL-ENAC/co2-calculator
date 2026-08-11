<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  RESULTS_CATEGORY_LABEL_KEYS,
  RESULTS_SUBCATEGORY_LABEL_KEYS,
} from 'src/constant/charts';
import { normalizeParentKey } from 'src/composables/useEmissionTreemap';
import type { EmissionBreakdownCategoryRow } from 'src/stores/modules';

interface RowTotal {
  key: string;
  label: string;
  tonnes: number;
  /** Physical quantity the backend derived for this bucket (km, kWh, kg…). */
  quantity: number;
  quantityUnit: string;
}

interface CategoryTotal extends RowTotal {
  children: RowTotal[];
}

const props = defineProps<{ categoryRows: EmissionBreakdownCategoryRow[] }>();

const { t, te, n } = useI18n();

function categoryLabel(categoryKey: string): string {
  const i18nKey = RESULTS_CATEGORY_LABEL_KEYS[categoryKey];
  return i18nKey ? t(i18nKey) : categoryKey;
}

// Same fallback ladder as the breakdown chart: mapped key, then a plain i18n
// key, then the raw taxonomy segment.
function subcategoryLabel(key: string): string {
  const i18nKey = RESULTS_SUBCATEGORY_LABEL_KEYS[key];
  if (i18nKey) return t(i18nKey);
  return te(key) ? t(key) : key;
}

/**
 * One row per emission category with its emission types nested one level
 * beneath it — the grouping the breakdown chart draws (`parent_key ?? key`),
 * read off the same rows so the report's numbers cannot drift from the app's.
 */
const totals = computed<CategoryTotal[]>(() =>
  props.categoryRows
    .map((row) => {
      const categoryKey = String(row.category_key ?? row.category ?? '');
      const byChild = new Map<string, { tonnes: number; quantity: number }>();
      let total = 0;
      let totalQuantity = 0;
      // One quantity unit per bucket, set by the backend-derived section.
      let quantityUnit = '';

      for (const emission of row.emissions) {
        const value = Number(emission.value) || 0;
        const quantity = Number(emission.quantity) || 0;
        if (value <= 0 && quantity <= 0) continue;
        const childKey = normalizeParentKey(
          categoryKey,
          String(emission.parent_key ?? emission.key),
        );
        const child = byChild.get(childKey) ?? { tonnes: 0, quantity: 0 };
        child.tonnes += value;
        child.quantity += quantity;
        byChild.set(childKey, child);
        total += value;
        totalQuantity += quantity;
        if (emission.quantity_unit) quantityUnit = emission.quantity_unit;
      }

      return {
        key: categoryKey,
        label: categoryLabel(categoryKey),
        tonnes: total,
        quantity: totalQuantity,
        quantityUnit,
        children: [...byChild.entries()]
          .sort(([, a], [, b]) => b.tonnes - a.tonnes)
          .map(([key, child]) => ({
            key,
            label: subcategoryLabel(key),
            tonnes: child.tonnes,
            quantity: child.quantity,
            quantityUnit,
          })),
      };
    })
    .filter((category) => category.tonnes > 0)
    .sort((a, b) => b.tonnes - a.tonnes),
);

/** Blank where the backend derives no physical quantity for that bucket. */
function quantityCell(row: RowTotal): string {
  if (row.quantity <= 0 || !row.quantityUnit) return '';
  return `${n(row.quantity, { maximumFractionDigits: 1 })} ${row.quantityUnit}`;
}

/** A report whose modules carry no physical quantity drops the column. */
const hasQuantities = computed(() =>
  totals.value.some((category) => category.quantity > 0),
);

const grandTotal = computed(() =>
  totals.value.reduce((sum, category) => sum + category.tonnes, 0),
);
</script>

<template>
  <table class="print-table">
    <thead>
      <tr>
        <th>{{ $t('planner_print_emission_types_col') }}</th>
        <th v-if="hasQuantities" class="align-right">
          {{ $t('planner_print_quantity_col') }}
        </th>
        <th class="align-right">{{ $t('planner_print_tonnes_col') }}</th>
      </tr>
    </thead>
    <tbody>
      <template v-for="category in totals" :key="category.key">
        <tr class="category-row">
          <td>{{ category.label }}</td>
          <td v-if="hasQuantities" class="align-right">
            {{ quantityCell(category) }}
          </td>
          <td class="align-right">
            {{
              $nOrDash(category.tonnes, {
                options: { maximumFractionDigits: 2 },
              })
            }}
          </td>
        </tr>
        <tr
          v-for="child in category.children"
          :key="`${category.key}-${child.key}`"
        >
          <td class="child-cell">{{ child.label }}</td>
          <td v-if="hasQuantities" class="align-right">
            {{ quantityCell(child) }}
          </td>
          <td class="align-right">
            {{
              $nOrDash(child.tonnes, { options: { maximumFractionDigits: 2 } })
            }}
          </td>
        </tr>
      </template>
    </tbody>
    <tfoot>
      <tr>
        <td class="text-weight-medium">{{ $t('planner_print_total_col') }}</td>
        <td v-if="hasQuantities"></td>
        <td class="align-right text-weight-medium">
          {{ $nOrDash(grandTotal, { options: { maximumFractionDigits: 2 } }) }}
        </td>
      </tr>
    </tfoot>
  </table>
</template>

<style scoped lang="scss">
.print-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 9px;

  th,
  td {
    border: 1px solid var(--half-muted-color);
    padding: 2px 4px;
    vertical-align: top;
  }

  th {
    text-align: left;
    font-weight: 600;
  }

  th.align-right,
  td.align-right {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
}

.category-row td {
  font-weight: 600;
}

.child-cell {
  padding-left: 16px;
}
</style>
