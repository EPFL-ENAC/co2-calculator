import { api } from '@/api/http';
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
    )
    .json<Record<string, TaxonomyNode>>();
}
