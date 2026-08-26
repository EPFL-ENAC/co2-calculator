import { api } from '@/api/http';
import { MODULES } from '@/constant/modules';
import {
  PLANNER_HEADCOUNT_CODES,
  PLANNER_HEADCOUNT_SUBMODULE,
} from '@/constant/planner-headcount';
import { buildModulePath } from '@/utils/modulePath';

export interface PlannerHeadcountRow {
  sius_code: string;
  fte: number;
}

export async function fetchPlannerHeadcountRows(
  carbonReportId: number,
): Promise<PlannerHeadcountRow[]> {
  const response = await api
    .get(
      `${buildModulePath(
        MODULES.Headcount,
        carbonReportId,
      )}/${PLANNER_HEADCOUNT_SUBMODULE}?page=1&limit=100`,
    )
    .json<{ items: { sius_code?: string; fte?: number | null }[] }>();

  const byCode = new Map(
    response.items
      .filter((item) => item.sius_code)
      .map((item) => [item.sius_code as string, item]),
  );
  // A blank category is the report saying "nobody here"; dropping it once means
  // neither the page list nor the table has to ask again what is filled in.
  const rows: PlannerHeadcountRow[] = [];
  for (const code of PLANNER_HEADCOUNT_CODES) {
    const fte = byCode.get(code)?.fte;
    if (fte != null) rows.push({ sius_code: code, fte });
  }
  return rows;
}
