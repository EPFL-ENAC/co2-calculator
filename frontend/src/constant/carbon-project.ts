/**
 * Which carbon project a page's module calls address.
 *
 * Each project stores its data in its own `carbon_reports` row, so this decides
 * where a page reads and — more importantly — writes. Pages declare it on their
 * route (`meta.carbonProject`); routes that declare nothing are the Calculator,
 * which is the only project addressed by unit + year.
 *
 * The values are names, not the legacy 0/1/2 codes: those were the
 * `carbon_project_type` query param the backend dropped in #1556, and the
 * backend's own enum is `CarbonReportType` ("Calculator" / "Simulator_Explore"
 * / "Simulator_Plan").
 */
export const CARBON_PROJECT = {
  calculator: 'calculator',
  explorer: 'explorer',
  planner: 'planner',
} as const;

export type CarbonProject =
  (typeof CARBON_PROJECT)[keyof typeof CARBON_PROJECT];

declare module 'vue-router' {
  interface RouteMeta {
    /** Simulator routes declare theirs; the Calculator's routes declare none. */
    carbonProject?: CarbonProject;
  }
}

export function resolveCarbonProject(
  meta: { carbonProject?: CarbonProject } | undefined,
): CarbonProject {
  return meta?.carbonProject ?? CARBON_PROJECT.calculator;
}

/**
 * The endpoint that resolves unit + year to this project's report id.
 *
 * A plan holds one report per year per plan, so unit/year cannot identify one:
 * planner callers pass the report id and never come here. Reaching this with
 * the planner is a bug, and it throws rather than falling back to the
 * Calculator — that fallback would write plan edits into real Calculator data.
 */
export function carbonReportLookupPath(
  project: CarbonProject,
  unit: number | string,
  year: number | string,
): string {
  const u = encodeURIComponent(unit);
  const y = encodeURIComponent(year);
  switch (project) {
    case CARBON_PROJECT.explorer:
      return `carbon-reports/simulator/explore/unit/${u}/reference-year/${y}/`;
    case CARBON_PROJECT.calculator:
      return `carbon-reports/unit/${u}/year/${y}/`;
    case CARBON_PROJECT.planner:
      throw new Error('Planner module calls must pass a carbonReportId');
  }
}
