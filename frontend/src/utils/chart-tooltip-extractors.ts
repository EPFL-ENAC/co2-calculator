import { formatTonnesForChart } from 'src/utils/number';

export type TooltipAxisParam = {
  axisValue?: unknown;
  seriesName?: string;
  value?: number | (number | null)[] | null;
  marker?: string;
};

export function normalizeAxisParams(raw: unknown): TooltipAxisParam[] {
  if (!Array.isArray(raw)) return [];
  return raw as TooltipAxisParam[];
}

export function extractSeriesValue(
  raw: TooltipAxisParam['value'],
): number | null {
  if (typeof raw === 'number') return raw;
  if (!Array.isArray(raw)) return null;
  return (raw.length >= 2 ? raw[1] : raw[0]) as number | null;
}

const INT_FORMATTER = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
});

export function formatTooltipTonnes(v: number | null): string {
  if (v == null) return '-';
  if (v < 0) return v.toFixed(1);
  return formatTonnesForChart(v);
}

export function formatTooltipPopulation(v: number | null): string {
  if (v == null) return '-';
  return INT_FORMATTER.format(Math.round(v));
}
