import { api, SLOW_REQUEST_TIMEOUT_MS } from '@/api/http';
import type { TaxonomyNode } from '@/constant/modules';

/**
 * Batch-fetch taxonomies for several data entry types of one module.
 *
 * Collapses a report page's ~11 sequential
 * `taxonomies/module/{module}/{data_entry}` calls into one call per
 * module (#2049 T6). Response is keyed by the exact `entries` values
 * passed in, matching the single-entry endpoint's per-entry shape.
 */
export async function getModuleDataEntriesTaxonomies(
  moduleType: string,
  entries: string[],
  year: string,
): Promise<Record<string, TaxonomyNode>> {
  const searchParams = new URLSearchParams({ year });
  for (const entry of entries) {
    searchParams.append('entries', entry);
  }
  return api
    .get(
      `taxonomies/module/${encodeURIComponent(moduleType)}/data-entries?${searchParams.toString()}`,
      // Batching (#2280) concentrated N single-entry calls into one request,
      // so this one carries the sum of work that used to be spread across N
      // separate timeouts — the slowest single entry measured 2064 ms
      // (#2049). Each entry hits the same server-side cache, so a warm call
      // is fast; a cold one right after an ingestion is what needs headroom.
      { timeout: SLOW_REQUEST_TIMEOUT_MS },
    )
    .json<Record<string, TaxonomyNode>>();
}
