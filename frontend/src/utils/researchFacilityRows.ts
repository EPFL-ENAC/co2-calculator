/**
 * Planner research-facility rows, derived from the taxonomy tree (#2391).
 *
 * The lookup endpoint returns facility nodes keyed by `researchfacility_id`,
 * labelled with the acronym users know (#2007), carrying the platform's
 * metric unit in `meta.use_unit`. Animal facilities nest one housing-type
 * node per row, and the unit is that child's — a facility can meter rodents
 * in housings and fish in tanks.
 *
 * Store-free leaf so it stays unit-testable, like `dataEntryPolicy.ts`.
 */

import type { TaxonomyNode } from '@/constant/modules';

export type RfSub = 'research-facilities' | 'animal_facilities';

export interface RfRow {
  key: string;
  sub: RfSub;
  facilityId: string;
  name: string;
  /** Animal facilities only (rodent / fish). */
  facilityType: string | null;
  /** The platform's metric — the factor's use unit. */
  metric: string;
  selected: boolean;
  use: number | null;
  /** Last persisted use — `blur` after `Enter` must not save twice. */
  saved: number | null;
  entryId: number | null;
  kg: number | null;
}

/** Animal rows are one per (facility, type); common rows one per facility. */
export function rowKey(
  sub: RfSub,
  facilityId: string,
  facilityType: string | null,
): string {
  return `${sub}:${facilityId}${facilityType ? `:${facilityType}` : ''}`;
}

/**
 * One row per selectable platform, sorted by name. A node without a metric is
 * not a usable row — the unit must string-equal the factor's or the emission
 * formula raises — so it is dropped, as the `use_unit` check on the raw
 * factor rows did before the migration.
 */
export function buildResearchFacilityRows(
  sub: RfSub,
  facilities: TaxonomyNode[],
): RfRow[] {
  return facilities
    .flatMap((facility) => {
      const leaves = facility.children?.length
        ? facility.children.map((type) => ({
            type: type.name,
            metric: type.meta?.use_unit,
          }))
        : [{ type: null, metric: facility.meta?.use_unit }];
      return leaves
        .filter((leaf) => typeof leaf.metric === 'string' && leaf.metric !== '')
        .map((leaf) => ({
          key: rowKey(sub, facility.name, leaf.type),
          sub,
          facilityId: facility.name,
          name: facility.label,
          facilityType: leaf.type,
          metric: leaf.metric as string,
          selected: false,
          use: null,
          saved: null,
          entryId: null,
          kg: null,
        }));
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}
