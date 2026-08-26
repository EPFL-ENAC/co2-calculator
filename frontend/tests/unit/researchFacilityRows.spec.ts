/**
 * #2391 decision 1 — the planner research-facility grid reads its rows off the
 * taxonomy tree instead of `factors/{det}/list`, which shipped every emission
 * coefficient to build four display fields. This pins the mapping: the node
 * name is the stored facility id, its label the acronym users pick by, the
 * subkind child the housing type, and `meta.use_unit` the row's metric.
 */

import { test, expect } from '@playwright/test';

import { buildResearchFacilityRows } from '../../src/utils/researchFacilityRows';

// research_facilities: kind_field = researchfacility_id, no subkind.
const COMMON_TREE = [
  { name: '1902', label: 'SCITAS-GE', meta: { use_unit: 'CHF' } },
  { name: '0872', label: 'CAM-GE', meta: { use_unit: '%' } },
];

// animal_facilities: same kind, subkind = researchfacility_type. The unit is a
// per-(facility, type) factor value, so it lives on the child node.
const ANIMAL_TREE = [
  {
    name: '1321',
    label: 'CPG',
    meta: { use_unit: 'housings' },
    children: [
      { name: 'rodent', label: 'Rodent', meta: { use_unit: 'housings' } },
      { name: 'fish', label: 'Fish', meta: { use_unit: 'tanks' } },
    ],
  },
];

test('a flat facility node becomes one row keyed by id, labelled by acronym', () => {
  expect(buildResearchFacilityRows('research-facilities', COMMON_TREE)).toEqual(
    [
      expect.objectContaining({
        key: 'research-facilities:0872',
        facilityId: '0872',
        name: 'CAM-GE',
        facilityType: null,
        metric: '%',
      }),
      expect.objectContaining({
        key: 'research-facilities:1902',
        facilityId: '1902',
        name: 'SCITAS-GE',
        facilityType: null,
        metric: 'CHF',
      }),
    ],
  );
});

test('each housing type is its own row, with its own metric', () => {
  const rows = buildResearchFacilityRows('animal_facilities', ANIMAL_TREE);

  expect(rows.map((r) => [r.key, r.facilityType, r.metric])).toEqual([
    ['animal_facilities:1321:rodent', 'rodent', 'housings'],
    ['animal_facilities:1321:fish', 'fish', 'tanks'],
  ]);
  // The facility name is the parent's label, not the housing type's.
  expect(rows.every((r) => r.name === 'CPG' && r.facilityId === '1321')).toBe(
    true,
  );
});

test('a node without a metric is not a selectable row', () => {
  // The unit must string-equal the factor's or the emission formula raises —
  // the same reason the pre-migration code filtered on `use_unit`.
  expect(
    buildResearchFacilityRows('research-facilities', [
      { name: '1902', label: 'SCITAS-GE' },
      { name: '0872', label: 'CAM-GE', meta: { use_unit: '' } },
    ]),
  ).toEqual([]);
});

test('rows start unselected and empty — entries bind afterwards', () => {
  const [row] = buildResearchFacilityRows('research-facilities', COMMON_TREE);
  expect(row).toMatchObject({
    selected: false,
    use: null,
    saved: null,
    entryId: null,
    kg: null,
  });
});
