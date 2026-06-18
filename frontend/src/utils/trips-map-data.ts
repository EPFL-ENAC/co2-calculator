// Pure data helpers for the trips map: leg aggregation and the unit-manager
// member filter. Kept free of i18n / maplibre / DOM imports so they can be
// unit-tested in a plain Node runner (the display helpers live in
// ./trips-map, which pulls in formatKgCo2eq → i18n).
import type { TripLeg } from 'src/stores/modules';

export interface AggregatedLeg {
  mode: 'plane' | 'train';
  from: [number, number];
  to: [number, number];
  fromName: string;
  toName: string;
  tripCount: number;
  totalKgCo2eq: number;
  // Direction-normalised identity of the route (mode + endpoint pair). Lets the
  // hover highlight match a traveler's raw legs to aggregated routes.
  key: string;
  // Distinct traveler names on this route, heaviest emitter first. Drives the
  // hover popup; empty when the legs carry no traveler (e.g. older data).
  travelers: string[];
}

// Canonical orientation of a route so A→B and B→A collapse together: the
// endpoint with the smaller (lng, lat) becomes "from". Numeric comparison (not
// string-lexical) gives a clean total order. Returns the oriented endpoints,
// their names, and the identity key — the single source of truth shared by
// aggregateLegs and travelerRouteKeys so they always agree.
export interface OrientedRoute {
  from: [number, number];
  to: [number, number];
  fromName: string;
  toName: string;
  key: string;
}

export function orientRoute(
  mode: 'plane' | 'train',
  a: [number, number],
  b: [number, number],
  aName = '',
  bName = '',
): OrientedRoute {
  const swap = b[0] < a[0] || (b[0] === a[0] && b[1] < a[1]);
  const from = swap ? b : a;
  const to = swap ? a : b;
  return {
    from,
    to,
    fromName: swap ? bName : aName,
    toName: swap ? aName : bName,
    key: `${mode}|${from[0]},${from[1]}|${to[0]},${to[1]}`,
  };
}

// Direction-normalised route identity so A→B and B→A collapse to one key.
export function routeKeyFor(
  mode: 'plane' | 'train',
  origin: [number, number],
  dest: [number, number],
): string {
  return orientRoute(mode, origin, dest).key;
}

export interface TravelerTotal {
  id: string;
  name: string;
  totalKgCo2eq: number;
}

// Merge raw legs into one route per (mode, endpoint-pair), summing trips and
// emissions. Direction is normalised so A→B and B→A collapse together. Sorted
// heaviest-emitting first.
export function aggregateLegs(
  legs: TripLeg[],
  modeFilter?: 'plane' | 'train',
): AggregatedLeg[] {
  const filtered = modeFilter
    ? legs.filter((l) => l.mode === modeFilter)
    : legs;

  type Bucket = Omit<AggregatedLeg, 'travelers'> & {
    travelers: Map<string, { name: string; kg: number }>;
  };
  const buckets = new Map<string, Bucket>();
  for (const l of filtered) {
    const { from, to, fromName, toName, key } = orientRoute(
      l.mode,
      [l.origin_lng, l.origin_lat],
      [l.destination_lng, l.destination_lat],
      l.origin_name,
      l.destination_name,
    );
    let bucket = buckets.get(key);
    if (!bucket) {
      bucket = {
        mode: l.mode,
        from,
        to,
        fromName,
        toName,
        tripCount: 0,
        totalKgCo2eq: 0,
        key,
        travelers: new Map(),
      };
      buckets.set(key, bucket);
    }
    bucket.tripCount += l.number_of_trips;
    bucket.totalKgCo2eq += l.kg_co2eq;
    const tid = l.traveler_id || l.traveler_name;
    if (tid) {
      const entry = bucket.travelers.get(tid);
      if (entry) entry.kg += l.kg_co2eq;
      else
        bucket.travelers.set(tid, {
          name: l.traveler_name || l.traveler_id,
          kg: l.kg_co2eq,
        });
    }
  }
  return [...buckets.values()]
    .map((bucket) => ({
      mode: bucket.mode,
      from: bucket.from,
      to: bucket.to,
      fromName: bucket.fromName,
      toName: bucket.toName,
      tripCount: bucket.tripCount,
      totalKgCo2eq: bucket.totalKgCo2eq,
      key: bucket.key,
      travelers: [...bucket.travelers.values()]
        .sort((x, y) => y.kg - x.kg)
        .map((tr) => tr.name),
    }))
    .sort((x, y) => y.totalKgCo2eq - x.totalKgCo2eq);
}

// Join headcount-roster display names onto raw legs by SCIPER. The trips-map
// API ships only the traveler SCIPER (in both traveler_id and traveler_name);
// the frontend resolves names from the headcount-members endpoint. Travelers
// absent from the roster keep their existing traveler_name (the SCIPER).
export function resolveTravelerNames(
  legs: TripLeg[],
  namesById: Map<string, string>,
): TripLeg[] {
  if (!namesById.size) return legs;
  return legs.map((l) => ({
    ...l,
    traveler_name: namesById.get(l.traveler_id) ?? l.traveler_name,
  }));
}

// Per-traveler emission totals across the raw legs, heaviest first. Drives the
// unit-manager member filter (only meaningful when the API returns >1 traveler,
// i.e. for principal/global scope). Legs without a traveler_id are ignored.
export function travelerTotals(legs: TripLeg[]): TravelerTotal[] {
  const buckets = new Map<string, TravelerTotal>();
  for (const l of legs) {
    if (!l.traveler_id) continue;
    const existing = buckets.get(l.traveler_id);
    if (existing) {
      existing.totalKgCo2eq += l.kg_co2eq;
    } else {
      buckets.set(l.traveler_id, {
        id: l.traveler_id,
        name: l.traveler_name || l.traveler_id,
        totalKgCo2eq: l.kg_co2eq,
      });
    }
  }
  return [...buckets.values()].sort((a, b) => b.totalKgCo2eq - a.totalKgCo2eq);
}

// Route keys travelled by one person — used to highlight their trips on hover
// (every other route is dimmed). Matches aggregateLegs' keys via routeKeyFor.
export function travelerRouteKeys(
  legs: TripLeg[],
  travelerId: string,
): Set<string> {
  const keys = new Set<string>();
  for (const l of legs) {
    if (l.traveler_id !== travelerId) continue;
    keys.add(
      routeKeyFor(
        l.mode,
        [l.origin_lng, l.origin_lat],
        [l.destination_lng, l.destination_lat],
      ),
    );
  }
  return keys;
}

// Which legs the map renders, given the current selection and hover. Base =
// the selected travelers' legs (all when `selected` is null). Hovering a member
// always reveals THEIR legs on top — even a deselected one — so their trips can
// be spotlighted; members who are neither selected nor hovered stay hidden.
export function legsToRender(
  legs: TripLeg[],
  selected: Set<string> | null,
  hovered: string | null,
): TripLeg[] {
  const base =
    selected === null ? legs : legs.filter((l) => selected.has(l.traveler_id));
  if (hovered === null || selected === null || selected.has(hovered)) {
    return base;
  }
  return base.concat(legs.filter((l) => l.traveler_id === hovered));
}

// Toggle one traveler in the member filter. The selection is either `null`
// (all travelers shown — the default) or an explicit Set. Flipping a member
// out of the "all" state materialises the full set first; re-selecting every
// member collapses back to `null` so "all" and "explicitly-all" stay
// indistinguishable downstream. `allIds` is the full roster.
export function toggleTravelerSelection(
  current: Set<string> | null,
  id: string,
  allIds: string[],
): Set<string> | null {
  const next = new Set(current ?? allIds);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next.size === allIds.length ? null : next;
}
