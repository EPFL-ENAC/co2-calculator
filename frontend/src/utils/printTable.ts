import type { ModuleField } from 'src/constant/moduleConfig';

export type PrintRow = Record<string, unknown>;

export interface PrintColumn {
  name: string;
  label: string;
  field: string;
  align: 'left' | 'right' | 'center';
  options?: Array<{ value: string; label: string }>;
  optionLabelPrefix?: string;
  optionLabelKey?: string;
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

export function buildPrintColumns(
  fields: ModuleField[],
  t: PrintTranslateFn,
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
          optionLabelPrefix: f.optionLabelPrefix,
          optionLabelKey: f.optionLabelKey,
          optionsId: f.optionsId,
        });
      });
    });

  return columns;
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
    if (userInstitutionalId != null) {
      return ctx.headcountMembers.get(userInstitutionalId) ?? '-';
    }
    return '-';
  }

  const val = row[col.field];
  if (val === undefined || val === null || val === '') return '-';

  if (col.name === 'kg_co2eq' || col.name === 't_co2eq') {
    return ctx.formatNumber(val as number, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }

  if (col.options && typeof val === 'string') {
    const option = col.options.find((opt) => opt.value === val);
    if (option) {
      return ctx.te(option.label) ? ctx.t(option.label) : option.label;
    }
  }

  if (col.optionLabelPrefix && typeof val === 'string') {
    const key = val.toLowerCase();
    return ctx.te(key) ? ctx.t(key) : val;
  }

  if (col.optionLabelKey && typeof val === 'string') {
    const key = col.optionLabelKey.replace('{value}', val.toLowerCase());
    return ctx.te(key) ? ctx.t(key) : val;
  }

  if (col.optionsId === 'kind' && typeof val === 'string') {
    return ctx.taxonomyKindLabels[val] ?? val;
  }

  if (typeof val === 'string') return val;
  if (typeof val === 'number') {
    return ctx.formatNumber(val, ctx.numberFormatOptions);
  }
  return String(val);
}
