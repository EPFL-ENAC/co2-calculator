import { MODULES } from 'src/constant/modules';
import { formatKgCo2eq } from 'src/utils/number';
import type { AggregatedLeg } from 'src/utils/trips-map-data';

// Pure aggregation + member-filter helpers live in ./trips-map-data (i18n-free
// so they're unit-testable in Node); re-exported here so callers have a single
// trips-map entry point.
export type { AggregatedLeg, TravelerTotal } from 'src/utils/trips-map-data';
export {
  aggregateLegs,
  travelerTotals,
  travelerRouteKeys,
  legsToRender,
  toggleTravelerSelection,
} from 'src/utils/trips-map-data';

// Turbo emissions ramp, right half only (green → red). The CSS gradient drives
// the legend; the maplibre expression drives the lines — same stops, two forms.
export const CO2_RAMP_CSS =
  'linear-gradient(to right, #1ae4b6 0%, #4bf57f 20%, #8fff49 40%, #c5ee36 55%, #f3c63a 70%, #fd902a 82%, #ef5911 92%, #c42503 100%)';

export const LINE_COLOR_EXPR = [
  'interpolate',
  ['linear'],
  ['get', 'intensity'],
  0,
  '#1ae4b6',
  0.2,
  '#4bf57f',
  0.4,
  '#8fff49',
  0.55,
  '#c5ee36',
  0.7,
  '#f3c63a',
  0.82,
  '#fd902a',
  0.92,
  '#ef5911',
  1,
  '#c42503',
];

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
// volume — each log-normalised across the visible routes. When `highlightKeys`
// is set (member hover), routes not in it get `dim: 1` so the paint layer greys
// them out; `null` means nothing is dimmed.
export function buildTripsGeoJson(
  legs: AggregatedLeg[],
  highlightKeys: Set<string> | null = null,
) {
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
    const dim = highlightKeys !== null && !highlightKeys.has(leg.key) ? 1 : 0;
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
        dim,
        // JSON-encoded: MapLibre stringifies array/object props on the way back
        // out of interaction events, so encode explicitly and parse in the popup.
        travelers: JSON.stringify(leg.travelers),
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

// ── Hover popup ──────────────────────────────────────────────────────────────
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function popupRow(label: string, value: string): string {
  return (
    `<div class="row justify-between no-wrap">` +
    `<span class="text-grey-7 q-mr-md">${label}</span>` +
    `<span class="text-weight-medium">${value}</span></div>`
  );
}

// Travelers come through MapLibre as a JSON string (see buildTripsGeoJson); be
// lenient and also accept a raw array (direct calls / tests).
function parseTravelers(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string' && value.length) {
    try {
      const parsed: unknown = JSON.parse(value);
      if (Array.isArray(parsed)) return parsed.map(String);
    } catch {
      /* not JSON — ignore */
    }
  }
  return [];
}

// HTML for the leg hover popup, built from a MapLibre feature's properties.
// Compact, styled only with Quasar utility classes (no custom CSS) on top of
// MapLibre's default popup card. `t` is passed in since i18n lives in the
// component (it accepts an optional plural count). text-black: the popup renders
// inside .module-charts, which sets a teal text colour — pin a neutral base so
// the title/values aren't tinted.
export function buildLegPopupHtml(
  props: Record<string, unknown> | null,
  t: (key: string, plural?: number) => string,
): string {
  const mode = String(props?.mode ?? '');
  const fromName = String(props?.fromName ?? '');
  const toName = String(props?.toName ?? '');
  const tripCount = Number(props?.tripCount ?? 0);
  const total = Number(props?.totalKgCo2eq ?? 0);
  const avg = tripCount > 0 ? total / tripCount : 0;
  const travelers = parseTravelers(props?.travelers);
  const k = `${MODULES.ProfessionalTravel}-trips-map`;

  // Travelers go last on a single line. The value sits flush right when it fits
  // (margin-left:auto), and when it's too long it fills the remaining width and
  // truncates with a trailing "…" (single-line text-overflow, which works with
  // any alignment — unlike the multi-line clamp). min-width:0 lets the flex item
  // shrink below its content so the ellipsis can kick in.
  let travelersBlock = '';
  if (travelers.length) {
    const label = t(`${k}-popup-travelers`, travelers.length);
    const names = travelers.join(', ');
    travelersBlock =
      `<div class="row no-wrap items-baseline q-mt-xs">` +
      `<span class="text-grey-7 q-mr-md">${label}</span>` +
      `<span class="ellipsis text-weight-medium" style="min-width:0;margin-left:auto">${escapeHtml(names)}</span>` +
      `</div>`;
  }

  return (
    `<div class="text-caption text-black" style="line-height:1.5; max-width:240px">` +
    `<div class="text-weight-bold q-mb-xs">${escapeHtml(fromName)} ↔ ${escapeHtml(toName)}</div>` +
    popupRow(t(`${k}-popup-mode`), escapeHtml(t(mode))) +
    popupRow(t(`${k}-legend-trips`), String(tripCount)) +
    popupRow(t(`${k}-legend-emissions`), escapeHtml(formatKgCo2eq(total))) +
    popupRow(t(`${k}-popup-avg`), escapeHtml(formatKgCo2eq(avg))) +
    travelersBlock +
    `</div>`
  );
}
