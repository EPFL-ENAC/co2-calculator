/**
 * Unit tests for the trips-map member filter helpers (issue #282 follow-up).
 *
 * A unit manager (principal) sees every member's trips merged on the map.
 * These helpers drive the "filter by member" panel: `travelerTotals` lists the
 * distinct travelers with their CO₂ totals, `toggleTravelerSelection` is the
 * checkbox state machine, and the two compose with `aggregateLegs` so that
 * de-selecting a member drops their legs before aggregation.
 */

import { test, expect } from '@playwright/test';
import type { TripLeg } from '../../src/stores/modules';
import {
  aggregateLegs,
  orientRoute,
  resolveTravelerNames,
  travelerTotals,
  travelerRouteKeys,
  legsToRender,
  toggleTravelerSelection,
} from '../../src/utils/trips-map-data';

const ids = (ls: { traveler_id: string }[]) =>
  [...new Set(ls.map((l) => l.traveler_id))].sort();

function leg(partial: Partial<TripLeg>): TripLeg {
  return {
    mode: 'plane',
    origin_lat: 46.2381,
    origin_lng: 6.109,
    destination_lat: 40.6413,
    destination_lng: -73.7781,
    origin_name: 'Geneva Airport',
    destination_name: 'JFK',
    kg_co2eq: 100,
    number_of_trips: 1,
    traveler_id: 'alice',
    traveler_name: 'Alice Dupont',
    ...partial,
  };
}

const LEGS: TripLeg[] = [
  leg({ traveler_id: 'alice', traveler_name: 'Alice Dupont', kg_co2eq: 100 }),
  leg({ traveler_id: 'alice', traveler_name: 'Alice Dupont', kg_co2eq: 50 }),
  leg({ traveler_id: 'bob', traveler_name: 'Bob Martin', kg_co2eq: 300 }),
  leg({ traveler_id: 'carol', traveler_name: 'Carol Rossi', kg_co2eq: 20 }),
];

test('resolveTravelerNames joins roster names by SCIPER, keeps fallback', () => {
  const raw = [
    leg({ traveler_id: '111', traveler_name: '111' }),
    leg({ traveler_id: '222', traveler_name: '222' }),
  ];
  const names = new Map([['111', 'Alice Dupont']]);
  const out = resolveTravelerNames(raw, names);
  expect(out.map((l) => l.traveler_name)).toEqual(['Alice Dupont', '222']);
  // Pure: original legs are not mutated.
  expect(raw[0]?.traveler_name).toBe('111');
});

test('resolveTravelerNames returns legs unchanged when roster is empty', () => {
  const raw = [leg({ traveler_id: '111', traveler_name: '111' })];
  expect(resolveTravelerNames(raw, new Map())).toBe(raw);
});

test('travelerTotals sums per traveler and sorts heaviest first', () => {
  const totals = travelerTotals(LEGS);
  expect(totals.map((t) => t.id)).toEqual(['bob', 'alice', 'carol']);
  expect(totals.map((t) => t.totalKgCo2eq)).toEqual([300, 150, 20]);
  expect(totals.find((t) => t.id === 'bob')?.name).toBe('Bob Martin');
});

test('travelerTotals falls back to id when name is empty', () => {
  const totals = travelerTotals([
    leg({ traveler_id: 'dave', traveler_name: '', kg_co2eq: 10 }),
  ]);
  expect(totals[0]?.name).toBe('dave');
});

test('travelerTotals ignores legs without a traveler id', () => {
  const totals = travelerTotals([
    leg({ traveler_id: '', traveler_name: '', kg_co2eq: 10 }),
  ]);
  expect(totals).toHaveLength(0);
});

test('toggleTravelerSelection materialises from "all" then drops one', () => {
  const all = ['alice', 'bob', 'carol'];
  const next = toggleTravelerSelection(null, 'carol', all);
  expect(next).not.toBeNull();
  expect([...(next as Set<string>)].sort()).toEqual(['alice', 'bob']);
});

test('toggleTravelerSelection collapses back to null when all re-selected', () => {
  const all = ['alice', 'bob'];
  const partial = new Set(['alice']);
  expect(toggleTravelerSelection(partial, 'bob', all)).toBeNull();
});

test('toggleTravelerSelection re-adds a previously removed member', () => {
  const all = ['alice', 'bob', 'carol'];
  const partial = new Set(['alice']);
  const next = toggleTravelerSelection(partial, 'bob', all);
  expect([...(next as Set<string>)].sort()).toEqual(['alice', 'bob']);
});

test('travelerRouteKeys returns a person’s routes, matching aggregateLegs keys', () => {
  const aliceKeys = travelerRouteKeys(LEGS, 'alice');
  expect(aliceKeys.size).toBe(1); // alice's two legs share one route
  const aliceAgg = aggregateLegs(LEGS.filter((l) => l.traveler_id === 'alice'));
  expect([...aliceKeys]).toEqual([aliceAgg[0]?.key]);
});

test('travelerRouteKeys is empty for an unknown traveler', () => {
  expect(travelerRouteKeys(LEGS, 'nobody').size).toBe(0);
});

test('orientRoute orders endpoints numerically, not lexically', () => {
  // lng 10 vs 2: a string compare puts "10,0" < "2,0" (wrong); numeric puts
  // 2 first. Either way A→B and B→A must collapse to the same key.
  const ab = orientRoute('plane', [10, 0], [2, 0], 'Ten', 'Two');
  const ba = orientRoute('plane', [2, 0], [10, 0], 'Two', 'Ten');
  expect(ab.from).toEqual([2, 0]);
  expect(ab.fromName).toBe('Two');
  expect(ab.key).toBe(ba.key);
});

test('travelerRouteKeys normalises direction (A→B equals B→A)', () => {
  const there = leg({
    traveler_id: 'x',
    origin_lng: 1,
    origin_lat: 1,
    destination_lng: 2,
    destination_lat: 2,
  });
  const back = leg({
    traveler_id: 'y',
    origin_lng: 2,
    origin_lat: 2,
    destination_lng: 1,
    destination_lat: 1,
  });
  const kx = [...travelerRouteKeys([there], 'x')][0];
  const ky = [...travelerRouteKeys([back], 'y')][0];
  expect(kx).toBe(ky);
});

test('legsToRender: null selection shows everyone (no hover)', () => {
  expect(ids(legsToRender(LEGS, null, null))).toEqual([
    'alice',
    'bob',
    'carol',
  ]);
});

test('legsToRender: selection hides the rest', () => {
  const sel = new Set(['alice']);
  expect(ids(legsToRender(LEGS, sel, null))).toEqual(['alice']);
});

test('legsToRender: hovering a deselected member reveals only them on top', () => {
  // bob selected; hover carol (deselected) → carol's legs are added, alice stays hidden.
  const sel = new Set(['bob']);
  expect(ids(legsToRender(LEGS, sel, 'carol'))).toEqual(['bob', 'carol']);
});

test('legsToRender: hovering an already-selected member adds nothing', () => {
  const sel = new Set(['bob']);
  expect(ids(legsToRender(LEGS, sel, 'bob'))).toEqual(['bob']);
});

test('aggregateLegs collects distinct travelers per route, heaviest first', () => {
  // All LEGS share the GVA↔JFK route → one aggregated leg. Sorted by each
  // person's emissions: bob 300, alice 100+50=150, carol 20.
  const [route] = aggregateLegs(LEGS);
  expect(route?.travelers).toEqual([
    'Bob Martin',
    'Alice Dupont',
    'Carol Rossi',
  ]);
});

test('filtering then aggregating drops a de-selected member’s emissions', () => {
  // Show only bob → only his 300 kg leg survives aggregation.
  const selected = new Set(['bob']);
  const filtered = LEGS.filter((l) => selected.has(l.traveler_id));
  const aggregated = aggregateLegs(filtered);
  const total = aggregated.reduce((s, a) => s + a.totalKgCo2eq, 0);
  expect(total).toBe(300);
});
