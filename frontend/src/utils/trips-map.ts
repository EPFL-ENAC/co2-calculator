import type { TripLeg } from 'src/stores/modules';

export interface AggregatedLeg {
  mode: 'plane' | 'train';
  from: [number, number];
  to: [number, number];
  fromName: string;
  toName: string;
  tripCount: number;
  totalKgCo2eq: number;
}

// Reversed-magma emissions ramp (low = pale gold, high = deep indigo). The CSS
// gradient drives the legend; the maplibre expression drives the lines — same
// stops, two forms.
export const CO2_RAMP_CSS =
  'linear-gradient(to right, #fec287, #de4968 40%, #8c2981 70%, #3b0f70)';

export const LINE_COLOR_EXPR = [
  'interpolate',
  ['linear'],
  ['get', 'intensity'],
  0,
  '#fec287',
  0.4,
  '#de4968',
  0.7,
  '#8c2981',
  1,
  '#3b0f70',
];

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

  const buckets = new Map<string, AggregatedLeg>();
  for (const l of filtered) {
    const a: [number, number] = [l.origin_lng, l.origin_lat];
    const b: [number, number] = [l.destination_lng, l.destination_lat];
    let from = a;
    let to = b;
    let fromName = l.origin_name;
    let toName = l.destination_name;
    if (`${b[0]},${b[1]}` < `${a[0]},${a[1]}`) {
      from = b;
      to = a;
      fromName = l.destination_name;
      toName = l.origin_name;
    }
    const key = `${l.mode}|${from[0]},${from[1]}|${to[0]},${to[1]}`;
    const existing = buckets.get(key);
    if (existing) {
      existing.tripCount += l.number_of_trips;
      existing.totalKgCo2eq += l.kg_co2eq;
    } else {
      buckets.set(key, {
        mode: l.mode,
        from,
        to,
        fromName,
        toName,
        tripCount: l.number_of_trips,
        totalKgCo2eq: l.kg_co2eq,
      });
    }
  }
  return [...buckets.values()].sort((a, b) => b.totalKgCo2eq - a.totalKgCo2eq);
}

// Quadratic-bezier arc between the endpoints, bowed `bulge` degrees off the
// midpoint (perpendicular to travel direction). Bulge 0 → a straight line.
export function arcPoints(
  from: [number, number],
  to: [number, number],
  bulge: number,
  segments = 64,
): [number, number][] {
  const [lng1, lat1] = from;
  const lat2 = to[1];
  let lng2 = to[0];
  // Unwrap across the antimeridian so long legs take the short way round.
  if (Math.abs(lng2 - lng1) > 180) {
    lng2 += lng2 > lng1 ? -360 : 360;
  }
  const dx = lng2 - lng1;
  const dy = lat2 - lat1;
  const dist = Math.hypot(dx, dy);
  if (dist === 0 || bulge === 0) return [from, [lng2, lat2]];

  const cx = (lng1 + lng2) / 2 + (-dy / dist) * bulge;
  const cy = (lat1 + lat2) / 2 + (dx / dist) * bulge;
  const pts: [number, number][] = [];
  for (let i = 0; i <= segments; i++) {
    const f = i / segments;
    const g = 1 - f;
    const lng = g * g * lng1 + 2 * g * f * cx + f * f * lng2;
    const lat = g * g * lat1 + 2 * g * f * cy + f * f * lat2;
    pts.push([lng, lat]);
  }
  return pts;
}

// Planes arc (curvature grows with distance, clamped); trains stay straight —
// shape alone separates the two modes.
export function baseBulge(
  from: [number, number],
  to: [number, number],
  mode: string,
): number {
  if (mode === 'train') return 0;
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  return Math.min(Math.max(Math.hypot(dx, dy) * 0.18, 0.7), 12);
}

// Log scale so the heavily skewed trip/emission distributions spread across the
// full 0..1 range instead of bunching at one end. A single value maps to 1.
export function logNorm(value: number, min: number, max: number): number {
  if (value <= 0 || min <= 0) return 0;
  const span = Math.log(max) - Math.log(min);
  return span > 0 ? (Math.log(value) - Math.log(min)) / span : 1;
}

// One LineString per route. Colour encodes emissions, width encodes trip
// volume — each log-normalised across the visible routes.
export function buildTripsGeoJson(legs: AggregatedLeg[]) {
  type GeoFeature = {
    type: 'Feature';
    properties: Record<string, unknown>;
    geometry: { type: 'LineString'; coordinates: [number, number][] };
  };
  const features: GeoFeature[] = [];
  let kgMin = Infinity;
  let kgMax = 0;
  let tripsMin = Infinity;
  let tripsMax = 0;
  for (const l of legs) {
    if (l.totalKgCo2eq > 0) {
      kgMin = Math.min(kgMin, l.totalKgCo2eq);
      kgMax = Math.max(kgMax, l.totalKgCo2eq);
    }
    if (l.tripCount > 0) {
      tripsMin = Math.min(tripsMin, l.tripCount);
      tripsMax = Math.max(tripsMax, l.tripCount);
    }
  }
  for (const leg of legs) {
    const intensity = logNorm(leg.totalKgCo2eq, kgMin, kgMax);
    const volume = logNorm(leg.tripCount, tripsMin, tripsMax);
    const lineWidth = 2.5 + volume * 5.5;
    const coords = arcPoints(
      leg.from,
      leg.to,
      baseBulge(leg.from, leg.to, leg.mode),
    );
    features.push({
      type: 'Feature',
      properties: {
        mode: leg.mode,
        fromName: leg.fromName,
        toName: leg.toName,
        tripCount: leg.tripCount,
        totalKgCo2eq: leg.totalKgCo2eq,
        intensity,
        lineWidth,
      },
      geometry: { type: 'LineString', coordinates: coords },
    });
  }
  return { type: 'FeatureCollection' as const, features };
}

// One Point per distinct endpoint across all routes (deduplicated).
export function buildEndpointFeatures(legs: AggregatedLeg[]) {
  const seen = new Map<string, [number, number]>();
  for (const leg of legs) {
    seen.set(`${leg.from[0]},${leg.from[1]}`, leg.from);
    seen.set(`${leg.to[0]},${leg.to[1]}`, leg.to);
  }
  return {
    type: 'FeatureCollection' as const,
    features: [...seen.values()].map((p) => ({
      type: 'Feature' as const,
      properties: {},
      geometry: { type: 'Point' as const, coordinates: p },
    })),
  };
}
