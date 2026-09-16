import type { EmissionBreakdownResponse } from '@/stores/modules';

/** One bar of the per-FTE chart: its x-axis label and per-FTE values by category. */
export interface PerPersonRow {
  label: string;
  perPersonBreakdown: Record<string, number>;
  /** Hatched like the comparison chart's "Detailed per year" bars. */
  hatched?: boolean;
}

/**
 * The Planner's per-FTE bars: one per results view that has headcount. The
 * Grant Proposal and the summed year sections sit side by side, never summed
 * (#1977, #2071); the years bar is hatched exactly as in
 * PlannerGrantComparisonChart. No bar at all means no headcount was entered.
 */
export function plannerPerFteRows(opts: {
  isGrantProposal: boolean;
  hasYearSections: boolean;
  grantBreakdown: EmissionBreakdownResponse | null;
  yearsBreakdown: EmissionBreakdownResponse | null;
  grantLabel: string;
  yearsLabel: string;
}): PerPersonRow[] {
  const views = [
    ...(opts.isGrantProposal
      ? [
          {
            label: opts.grantLabel,
            breakdown: opts.grantBreakdown,
            hatched: false,
          },
        ]
      : []),
    ...(!opts.isGrantProposal || opts.hasYearSections
      ? [
          {
            label: opts.yearsLabel,
            breakdown: opts.yearsBreakdown,
            hatched: opts.isGrantProposal,
          },
        ]
      : []),
  ];
  return views.flatMap((view) =>
    view.breakdown && view.breakdown.total_fte > 0
      ? [
          {
            label: view.label,
            perPersonBreakdown: view.breakdown.per_person_breakdown,
            hatched: view.hatched,
          },
        ]
      : [],
  );
}
