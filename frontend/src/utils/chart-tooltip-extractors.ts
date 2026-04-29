import type {
  TooltipRow,
  TooltipState,
} from '../composables/useEchartsTooltip';

// Inlined to avoid pulling in the i18n boot dependency from number.ts
function formatTonnesForChart(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1) return value.toFixed(0);
  if (abs >= 0.1) return value.toFixed(1);
  return value.toFixed(2);
}

type SeriesConfig = { name: string; encode: { y: string } };

// ─── EvolutionOverTimeChart ────────────────────────────────────────────────

export function extractEvolutionTooltipState(params: unknown): TooltipState {
  const p = params as Array<{
    seriesName?: string;
    value?: number;
    color?: string;
    axisValue?: string | number;
  }>;
  if (!Array.isArray(p) || p.length === 0) return null;

  return {
    title: p[0].axisValue != null ? String(p[0].axisValue) : undefined,
    rows: p.map((item) => ({
      label: item.seriesName ?? '',
      value: String(item.value?.toFixed(0) ?? ''),
      color: item.color ?? '',
    })),
  };
}

// ─── ModuleCarbonFootprintChart ───────────────────────────────────────────

type TFn = (key: string, options?: Record<string, unknown>) => string;

export function extractModuleCarbonTooltipState(
  params: unknown,
  seriesArray: SeriesConfig[],
  validatedLabels: Set<string>,
  additionalHeadcountLabels: Set<string>,
  additionalBuildingsLabels: Set<string>,
  t: TFn,
): TooltipState {
  const arr = Array.isArray(params)
    ? (params as unknown[])
    : params
      ? [params]
      : [];
  if (!arr.length) return null;

  const first = arr[0] as {
    data?: Record<string, unknown>;
    axisValue?: string;
    name?: string;
  };
  const name = first.axisValue || first.name || '';

  if (!validatedLabels.has(name)) {
    const moduleName = additionalHeadcountLabels.has(name)
      ? t('headcount')
      : additionalBuildingsLabels.has(name)
        ? t('buildings')
        : name;
    return {
      title: name,
      rows: [],
      tone: 'muted',
      footer: t('results_validate_module_title', { module: moduleName }),
    };
  }

  const data = first.data;
  let total = 0;
  const rows: TooltipRow[] = [];

  arr
    .slice()
    .reverse()
    .forEach((item) => {
      const p = item as {
        seriesName?: string;
        seriesIndex?: number;
        color?: string;
      };
      const series =
        typeof p.seriesIndex === 'number'
          ? seriesArray[p.seriesIndex]
          : seriesArray.find((s) => s.name === p.seriesName);
      const key = series?.encode.y;
      if (!data || !key) return;
      const dataValue = Number(data[key]) || 0;
      if (dataValue > 0) {
        rows.push({
          label: series?.name || p.seriesName || '',
          value: formatTonnesForChart(dataValue),
          color: p.color ?? '',
        });
        total += dataValue;
      }
    });

  return {
    title: name,
    rows,
    footer: `Total: ${formatTonnesForChart(total)}`,
  };
}

// ─── CarbonFootPrintPerPersonChart ────────────────────────────────────────

export function extractPerPersonTooltipState(
  params: unknown,
  seriesArray: SeriesConfig[],
): TooltipState {
  const arr = Array.isArray(params)
    ? (params as unknown[])
    : params
      ? [params]
      : [];
  if (!arr.length) return null;

  const first = arr[0] as {
    data?: Record<string, unknown>;
    axisValue?: string;
    name?: string;
  };
  const name = (first.axisValue || first.name || '') as string;
  const data = first.data;

  let total = 0;
  const rows: TooltipRow[] = [];

  arr
    .slice()
    .reverse()
    .forEach((item) => {
      const p = item as { seriesName?: string; color?: string };
      const series = seriesArray.find((s) => s.name === p.seriesName);
      const key = series?.encode.y;
      const dataValue = Number(data?.[key ?? '']) || 0;
      if (dataValue > 0) {
        rows.push({
          label: series?.name || p.seriesName || '',
          value: formatTonnesForChart(dataValue),
          color: p.color ?? '',
        });
        total += dataValue;
      }
    });

  return {
    title: name,
    rows,
    footer: `Total: ${formatTonnesForChart(total)}`,
  };
}

// ─── ItFocusSection ───────────────────────────────────────────────────────

export function extractItFocusTooltipState(
  params: unknown,
  validatedLabels: Set<string>,
  t: TFn,
): TooltipState {
  const p = params as {
    seriesName?: string;
    value?: number;
    name?: string;
    color?: string;
  };
  const name = p.name || '';

  if (!validatedLabels.has(name)) {
    return {
      title: name,
      rows: [],
      tone: 'muted',
      footer: t('results_validate_module_title', { module: name }),
    };
  }

  const val = Number(p.value) || 0;
  if (val <= 0) return null;

  return {
    rows: [
      {
        label: p.seriesName ?? '',
        value: `${formatTonnesForChart(val)}${t('results_units_tonnes')}`,
        color: p.color ?? '',
      },
    ],
  };
}

// ─── GenericEmissionTreeMapChart ──────────────────────────────────────────

export function extractTreemapTooltipState(
  params: unknown,
  t: TFn,
): TooltipState {
  const p = params as {
    seriesName?: string;
    data?: { originalValue: number };
    color?: string;
  };
  const val = p.data?.originalValue ?? 0;
  if (val <= 0) return null;

  return {
    rows: [
      {
        label: p.seriesName ?? '',
        value: `${formatTonnesForChart(val)}${t('results_units_tonnes')}`,
        color: p.color ?? '',
      },
    ],
  };
}

// ─── EmissionTypeBreakdownChart ───────────────────────────────────────────

export function extractEmissionBreakdownTooltipState(
  params: unknown,
  segmentKeys: string[],
  t: TFn,
): TooltipState {
  const p = params as {
    seriesName?: string;
    seriesIndex?: number;
    data?: Record<string, unknown>;
    color?: string;
  };
  const dimKey = segmentKeys[p.seriesIndex ?? 0];
  const val = p.data && dimKey !== undefined ? Number(p.data[dimKey]) || 0 : 0;
  if (val <= 0) return null;

  return {
    rows: [
      {
        label: p.seriesName ?? '',
        value: `${formatTonnesForChart(val)}${t('results_units_tonnes')}`,
        color: p.color ?? '',
      },
    ],
  };
}

// ─── ReductionObjective charts (shared helpers) ───────────────────────────

type TooltipAxisParam = {
  seriesName?: unknown;
  value?: unknown;
  axisValue?: unknown;
  color?: string;
};

function normalizeAxisParams(rawParams: unknown): TooltipAxisParam[] {
  if (!Array.isArray(rawParams)) return [];
  return rawParams as TooltipAxisParam[];
}

function extractAxisSeriesValue(raw: unknown): number | null {
  if (typeof raw === 'number') return raw;
  if (!Array.isArray(raw)) return null;
  return (raw.length >= 2 ? raw[1] : raw[0]) as number | null;
}

function formatTooltipTonnes(value: number | null): string {
  if (value == null) return '-';
  if (value < 0) return value.toFixed(1);
  return formatTonnesForChart(value);
}

type ReductionObjectiveOpts = {
  categoryColor: (key: string) => string;
  categoryLabel: (key: string) => string;
  tooltipSortIndex: (key: string) => number;
  populationLabel: string;
  formatPopulation: (value: number | null) => string;
};

// ─── ReductionObjectiveEpflView ───────────────────────────────────────────

export function extractReductionObjectiveEpflTooltipState(
  rawParams: unknown,
  opts: ReductionObjectiveOpts & {
    years: number[];
    accentColor: string;
    totalLabel: string;
  },
): TooltipState {
  const params = normalizeAxisParams(rawParams);
  if (!params.length) return null;

  const rawAxisValue = params[0]?.axisValue ?? '';
  const n = Number(rawAxisValue);
  let yearLabel: string;
  if (!Number.isFinite(n)) {
    yearLabel = String(rawAxisValue);
  } else if (opts.years.length > 0 && n >= opts.years[0]) {
    // category axis sends the actual year value (e.g. 2022) — use it directly
    yearLabel = String(Math.round(n));
  } else {
    // linked value axis sends a numeric index (e.g. 3.5) — map to year
    const idx = Math.min(
      Math.max(Math.round(n), 0),
      Math.max(opts.years.length - 1, 0),
    );
    yearLabel = String(opts.years[idx] ?? rawAxisValue);
  }

  // Total row
  const totalParam = params.find(
    (x) => String(x.seriesName) === 'total' && x.value != null,
  );
  const rows: TooltipRow[] = [];
  if (totalParam) {
    rows.push({
      label: opts.totalLabel,
      value: formatTooltipTonnes(extractAxisSeriesValue(totalParam.value)),
      color: opts.accentColor,
    });
  }

  // Category rows
  params
    .filter((p) => p.seriesName && p.value != null)
    .filter(
      (p) =>
        String(p.seriesName) !== 'population' &&
        String(p.seriesName) !== 'total',
    )
    .sort(
      (a, b) =>
        opts.tooltipSortIndex(String(a.seriesName ?? '')) -
        opts.tooltipSortIndex(String(b.seriesName ?? '')),
    )
    .forEach((p) => {
      const key = String(p.seriesName);
      rows.push({
        label: opts.categoryLabel(key),
        value: formatTooltipTonnes(extractAxisSeriesValue(p.value)),
        color: opts.categoryColor(key),
      });
    });

  // Population separator row
  const popParam = params.find(
    (x) => String(x.seriesName) === 'population' && x.value != null,
  );
  const separatorRow: TooltipRow | undefined = popParam
    ? {
        label: opts.populationLabel,
        value: opts.formatPopulation(extractAxisSeriesValue(popParam.value)),
        color: '#ff0000',
      }
    : undefined;

  return { title: yearLabel, rows, separatorRow };
}

// ─── ReductionObjectiveUnitView ───────────────────────────────────────────

export function extractReductionObjectiveUnitTooltipState(
  rawParams: unknown,
  opts: ReductionObjectiveOpts,
): TooltipState {
  const params = normalizeAxisParams(rawParams);
  if (!params.length) return null;

  const yearLabel = String(params[0]?.axisValue ?? '');

  // Category rows (excluding population)
  const rows: TooltipRow[] = [];
  params
    .filter((p) => p.seriesName && p.value != null)
    .filter((p) => String(p.seriesName) !== 'population')
    .sort(
      (a, b) =>
        opts.tooltipSortIndex(String(a.seriesName ?? '')) -
        opts.tooltipSortIndex(String(b.seriesName ?? '')),
    )
    .forEach((p) => {
      const key = String(p.seriesName);
      rows.push({
        label: opts.categoryLabel(key),
        value: formatTooltipTonnes(extractAxisSeriesValue(p.value)),
        color: opts.categoryColor(key),
      });
    });

  // Population separator row
  const popParam = params.find(
    (x) => String(x.seriesName) === 'population' && x.value != null,
  );
  const separatorRow: TooltipRow | undefined = popParam
    ? {
        label: opts.populationLabel,
        value: opts.formatPopulation(extractAxisSeriesValue(popParam.value)),
        color: '#ff0000',
      }
    : undefined;

  return { title: yearLabel, rows, separatorRow };
}

// ─── useAdditionalCategoryCharts (doughnut) ───────────────────────────────

export function extractDoughnutTooltipState(params: unknown): TooltipState {
  const p = params as { name?: unknown; percent?: unknown; color?: string };
  const name = String(p.name ?? '');
  const percent = typeof p.percent === 'number' ? p.percent : Number(p.percent);
  const percentDisplay = Number.isFinite(percent) ? percent.toFixed(0) : '0';

  return {
    rows: [{ label: name, value: `${percentDisplay}%`, color: p.color ?? '' }],
  };
}
