import { api } from '@/api/http';
import { i18n } from '@/boot/i18n';
import type { TaxonomyNode } from '@/constant/modules';

/**
 * Current locale as the short code the backend's translation table stores
 * (#2401): `'fr-CH'` -> `'fr'`. Normalized again server-side, but sending
 * the short code here means the taxonomy cache (frontend and backend) is
 * keyed on the same value the request actually needs.
 */
function currentLang(): string {
  return i18n.global.locale.value.split('-')[0];
}

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
  const searchParams = new URLSearchParams({ year, lang: currentLang() });
  for (const entry of entries) {
    searchParams.append('entries', entry);
  }
  return api
    .get(
      `taxonomies/module/${encodeURIComponent(moduleType)}/data-entries?${searchParams.toString()}`,
    )
    .json<Record<string, TaxonomyNode>>();
}

/**
 * One data entry type's taxonomy — the single lookup endpoint for form
 * options (#2391 decision 1): classification names, labels, and whatever
 * display metadata the module's handler whitelists. It replaced
 * `factors/{det}/class-subclass-map` and `factors/{det}/list`, which shipped
 * every emission coefficient alongside the names.
 */
export interface FactorOption {
  /** Stored classification value the form submits (purchase: UNSPSC code). */
  name: string;
  /** Request-locale display text. */
  label: string;
}

/**
 * Server-side typeahead over one data entry type's classification options
 * (#2391 decision 4) — for option lists too large to ship as a taxonomy
 * tree. Matches the stored value, the English label text, and its
 * translated label; `query` needs at least 2 characters.
 */
export async function searchDataEntryOptions(
  moduleType: string,
  dataEntry: string,
  query: string,
  year: number | string,
  limit = 50,
): Promise<FactorOption[]> {
  const searchParams = new URLSearchParams({
    query,
    year: String(year),
    lang: currentLang(),
    limit: String(limit),
  });
  return api
    .get(
      `taxonomies/module/${encodeURIComponent(moduleType)}/${encodeURIComponent(dataEntry)}/options?${searchParams.toString()}`,
    )
    .json<FactorOption[]>();
}

export async function getDataEntryTaxonomy(
  moduleType: string,
  dataEntry: string,
  year: number | string,
): Promise<TaxonomyNode> {
  const searchParams = new URLSearchParams({
    year: String(year),
    lang: currentLang(),
  });
  return api
    .get(
      `taxonomies/module/${encodeURIComponent(moduleType)}/${encodeURIComponent(dataEntry)}?${searchParams.toString()}`,
    )
    .json<TaxonomyNode>();
}
