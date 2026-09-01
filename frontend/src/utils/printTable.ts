import type { ModuleField } from '@/constant/moduleConfig';
import { resolveTravelerName } from '@/constant/module-config/traveler-options';

export type PrintRow = Record<string, unknown>;

export interface PrintColumn {
  name: string;
  label: string;
  field: string;
  align: 'left' | 'right' | 'center';
  options?: Array<{ value: string; label: string }>;
  optionLabelsFromTaxonomy?: boolean;
  optionsId?: string;
}

export type PrintTranslateFn = (
  key: string,
  params?: Record<string, unknown>,
) => string;

export interface PrintCellContext {
  t: PrintTranslateFn;
  te: (key: string) => boolean;
  taxonomyKindLabels: Record<string, string>;
  headcountMembers: Map<string, string>;
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
  numberFormatOptions?: Intl.NumberFormatOptions;
}

/**
 * Planner prefilled tables carry the reference-year kgCO₂eq and the "% of
 * reference year" the row was scaled by — the two values that explain how a
 * planned figure was derived. Mirrors the column placement ModuleTable uses
 * on screen: reference before the current kgCO₂eq, percentage after it.
 */
function withReferenceColumns(
  columns: PrintColumn[],
  t: PrintTranslateFn,
): PrintColumn[] {
  const referenceColumn: PrintColumn = {
    name: 'reference_kg_co2eq',
    label: t('planner_reference_kg_col'),
    field: 'reference_kg_co2eq',
    align: 'right',
  };
  const percentageColumn: PrintColumn = {
    name: 'percentage_of_reference_year',
    label: t('planner_percentage_col'),
    field: 'percentage_of_reference_year',
    align: 'right',
  };

  const kgIndex = columns.findIndex((column) => column.name === 'kg_co2eq');
  if (kgIndex < 0) return [...columns, referenceColumn, percentageColumn];
  return [
    ...columns.slice(0, kgIndex),
    referenceColumn,
    columns[kgIndex] as PrintColumn,
    percentageColumn,
    ...columns.slice(kgIndex + 1),
  ];
}

export function buildPrintColumns(
  fields: ModuleField[],
  t: PrintTranslateFn,
  showReferenceColumns = false,
): PrintColumn[] {
  const columns: PrintColumn[] = [];

  fields
    .filter((f) => !f.hideIn?.table)
    .forEach((f) => {
      const labelKeys = Array.isArray(f.labelKey) ? f.labelKey : [f.labelKey];

      labelKeys.forEach((labelKey, index) => {
        let label = f.unit ? `${f.label ?? ''} (${f.unit})` : (f.label ?? '');
        if (labelKey) {
          const translated = t(labelKey, { unit: f.unit });
          if (translated) {
            label = translated;
          }
        }

        columns.push({
          name: Array.isArray(f.labelKey) ? `${f.id}_${index}` : f.id,
          label,
          field: f.id,
          align: f.align ?? 'left',
          options: f.options,
          optionLabelsFromTaxonomy: f.optionLabelsFromTaxonomy,
          optionsId: f.optionsId,
        });
      });
    });

  return showReferenceColumns ? withReferenceColumns(columns, t) : columns;
}

export function renderPrintCell(
  row: PrintRow,
  col: PrintColumn,
  ctx: PrintCellContext,
): string {
  if (col.field === 'origin_name') {
    const name = row['origin_name'] as string | undefined;
    const iata = row['origin_iata'] as string | undefined;
    return iata ? `${name ?? iata} (${iata})` : (name ?? '-');
  }
  if (col.field === 'destination_name') {
    const name = row['destination_name'] as string | undefined;
    const iata = row['destination_iata'] as string | undefined;
    return iata ? `${name ?? iata} (${iata})` : (name ?? '-');
  }
  if (col.field === 'traveler_name') {
    const userInstitutionalId = row['user_institutional_id'] as
      string | undefined;
    return resolveTravelerName(
      userInstitutionalId,
      userInstitutionalId != null
        ? ctx.headcountMembers.get(userInstitutionalId)
        : undefined,
      ctx.t,
    );
  }

  const val = row[col.field];
  if (val === undefined || val === null || val === '') return '-';

  if (
    col.name === 'kg_co2eq' ||
    col.name === 't_co2eq' ||
    col.name === 'reference_kg_co2eq'
  ) {
    return ctx.formatNumber(val as number, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }

  if (col.name === 'percentage_of_reference_year') {
    return `${ctx.formatNumber(val as number, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}%`;
  }

  // Label sources, in order: i18n-keyed static options (travel cabin
  // classes), then the backend taxonomy labels — vocabulary selects
  // (sius_code, room_type) and kind/subkind columns alike (#2613).
  if (typeof val === 'string') {
    const option = col.options?.find((opt) => opt.value === val);
    if (option && ctx.te(option.label)) return ctx.t(option.label);

    if (
      col.optionLabelsFromTaxonomy ||
      col.optionsId === 'kind' ||
      col.optionsId === 'subkind'
    ) {
      return ctx.taxonomyKindLabels[val] ?? val;
    }

    return option?.label ?? val;
  }

  if (typeof val === 'number') {
    return ctx.formatNumber(val, ctx.numberFormatOptions);
  }
  return String(val);
}
