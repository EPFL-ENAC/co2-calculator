import { api } from '@/api/http';
import type {
  Module,
  Submodule as SubmoduleResponse,
} from '@/constant/modules';
import { buildModulePath } from '@/utils/modulePath';
import type { PrintRow } from '@/utils/printTable';

/** The API caps `limit` at 1000, so that is the largest page worth asking for. */
const PAGE_LIMIT = 1000;

/**
 * Every row of one submodule, following pagination to the end — a print report
 * shows the whole table, not the first page of it.
 */
export async function fetchAllSubmoduleRows(
  moduleType: Module,
  submoduleId: string,
  carbonReportId: number,
): Promise<PrintRow[]> {
  const basePath = `${buildModulePath(
    moduleType,
    carbonReportId,
  )}/${encodeURIComponent(submoduleId)}`;

  const rows: PrintRow[] = [];
  let page = 1;
  for (;;) {
    const queryParams = new URLSearchParams({
      page: String(page),
      limit: String(PAGE_LIMIT),
    });
    const response = (await api
      .get(`${basePath}?${queryParams.toString()}`)
      .json()) as SubmoduleResponse;
    rows.push(...(response.items as unknown as PrintRow[]));
    if (!response.items.length || rows.length >= response.summary.total_items) {
      break;
    }
    page += 1;
  }
  return rows;
}
