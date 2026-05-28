<template>
  <div
    class="trips-map"
    :style="{ height }"
    role="img"
    :aria-label="ariaLabel"
    :data-testid="testid"
  >
    <q-skeleton v-if="loading && !visibleLegs.length" :height="height" />
    <div
      v-else-if="!visibleLegs.length"
      class="column flex-center full-height text-center q-pa-md text-body2 text-secondary"
    >
      <q-icon name="map" size="lg" class="text-grey-6 q-mb-sm" />
      {{ t(`${MODULES.ProfessionalTravel}-trips-map-empty`) }}
    </div>
    <template v-else>
      <div ref="mapEl" class="trips-map__canvas" />
      <ul class="trips-map__sr-only">
        <li v-for="(leg, idx) in visibleLegs" :key="idx">
          {{
            t(`${MODULES.ProfessionalTravel}-trips-map-leg-aria`, {
              from: leg.fromName,
              to: leg.toName,
              count: leg.tripCount,
              emissions: formatKgCo2eq(leg.totalKgCo2eq),
            })
          }}
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { runtimeConfig } from 'src/config/runtime';
import { MODULES } from 'src/constant/modules';

interface RawLeg {
  mode: 'plane' | 'train';
  origin_lat: number;
  origin_lng: number;
  destination_lat: number;
  destination_lng: number;
  origin_name: string;
  destination_name: string;
  kg_co2eq: number;
  number_of_trips: number;
}

interface AggregatedLeg {
  mode: 'plane' | 'train';
  from: [number, number];
  to: [number, number];
  fromName: string;
  toName: string;
  tripCount: number;
  totalKgCo2eq: number;
}

const props = withDefaults(
  defineProps<{
    legs: RawLeg[];
    modeFilter?: 'plane' | 'train';
    aggregation?: 'undirected' | 'directed' | 'none';
    height?: string;
    loading?: boolean;
    ariaLabel?: string;
    testid?: string;
  }>(),
  {
    aggregation: 'undirected',
    height: '360px',
    loading: false,
    ariaLabel: 'Trips map',
    testid: 'trips-map',
    modeFilter: undefined,
  },
);

const { t } = useI18n();

const PLANE_COLOR = '#e65100';
const TRAIN_COLOR = '#1b5e20';

const visibleLegs = computed<AggregatedLeg[]>(() => {
  const filtered = props.modeFilter
    ? props.legs.filter((l) => l.mode === props.modeFilter)
    : props.legs;

  if (props.aggregation === 'none') {
    return filtered.map((l) => ({
      mode: l.mode,
      from: [l.origin_lng, l.origin_lat],
      to: [l.destination_lng, l.destination_lat],
      fromName: l.origin_name,
      toName: l.destination_name,
      tripCount: l.number_of_trips,
      totalKgCo2eq: l.kg_co2eq,
    }));
  }

  const buckets = new Map<string, AggregatedLeg>();
  for (const l of filtered) {
    const a: [number, number] = [l.origin_lng, l.origin_lat];
    const b: [number, number] = [l.destination_lng, l.destination_lat];
    let from = a;
    let to = b;
    let fromName = l.origin_name;
    let toName = l.destination_name;
    if (
      props.aggregation === 'undirected' &&
      `${b[0]},${b[1]}` < `${a[0]},${a[1]}`
    ) {
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
  return [...buckets.values()];
});

const mapEl = ref<HTMLDivElement | null>(null);
let map: unknown = null;
let MapLibreNS: unknown = null;
let resizeObserver: ResizeObserver | null = null;

function formatKgCo2eq(kg: number): string {
  if (kg >= 1000) return `${(kg / 1000).toFixed(1)} t CO₂eq`;
  return `${kg.toFixed(0)} kg CO₂eq`;
}

function greatCirclePoints(
  from: [number, number],
  to: [number, number],
  segments = 64,
): [number, number][][] {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const toDeg = (r: number) => (r * 180) / Math.PI;
  const lat1 = toRad(from[1]);
  const lng1 = toRad(from[0]);
  const lat2 = toRad(to[1]);
  const lng2 = toRad(to[0]);
  const d =
    2 *
    Math.asin(
      Math.sqrt(
        Math.sin((lat2 - lat1) / 2) ** 2 +
          Math.cos(lat1) * Math.cos(lat2) * Math.sin((lng2 - lng1) / 2) ** 2,
      ),
    );
  if (d === 0) return [[from, to]];

  const pts: [number, number][] = [];
  for (let i = 0; i <= segments; i++) {
    const f = i / segments;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x =
      A * Math.cos(lat1) * Math.cos(lng1) + B * Math.cos(lat2) * Math.cos(lng2);
    const y =
      A * Math.cos(lat1) * Math.sin(lng1) + B * Math.cos(lat2) * Math.sin(lng2);
    const z = A * Math.sin(lat1) + B * Math.sin(lat2);
    const lat = Math.atan2(z, Math.sqrt(x * x + y * y));
    const lng = Math.atan2(y, x);
    pts.push([toDeg(lng), toDeg(lat)]);
  }

  // Split at the antimeridian so the line takes the short way around.
  const segs: [number, number][][] = [];
  let current: [number, number][] = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    if (Math.abs(pts[i][0] - pts[i - 1][0]) > 180) {
      segs.push(current);
      current = [pts[i]];
    } else {
      current.push(pts[i]);
    }
  }
  segs.push(current);
  return segs;
}

function buildGeoJson(legs: AggregatedLeg[]) {
  type GeoFeature = {
    type: 'Feature';
    properties: Record<string, unknown>;
    geometry: { type: 'LineString'; coordinates: [number, number][] };
  };
  const features: GeoFeature[] = [];
  for (const leg of legs) {
    const segs =
      leg.mode === 'plane'
        ? greatCirclePoints(leg.from, leg.to)
        : [[leg.from, leg.to] as [number, number][]];
    for (const coords of segs) {
      features.push({
        type: 'Feature',
        properties: {
          mode: leg.mode,
          fromName: leg.fromName,
          toName: leg.toName,
          tripCount: leg.tripCount,
          totalKgCo2eq: leg.totalKgCo2eq,
        },
        geometry: { type: 'LineString', coordinates: coords },
      });
    }
  }
  return { type: 'FeatureCollection' as const, features };
}

function endpointFeatures(legs: AggregatedLeg[]) {
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

async function ensureMap() {
  if (!mapEl.value) return;
  if (!MapLibreNS) {
    MapLibreNS = await import('maplibre-gl');
    await import('maplibre-gl/dist/maplibre-gl.css');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ml = MapLibreNS as any;
  if (map) return;
  map = new ml.Map({
    container: mapEl.value,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: [runtimeConfig.mapTileStyleUrl],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [
        {
          id: 'osm',
          type: 'raster',
          source: 'osm',
          paint: { 'raster-saturation': -1 },
        },
      ],
    },
    center: [6.6323, 46.5197],
    zoom: 3,
    attributionControl: false,
  });
  (map as InstanceType<typeof ml.Map>).addControl(
    new ml.NavigationControl(),
    'top-right',
  );
  await new Promise<void>((resolve) =>
    (map as InstanceType<typeof ml.Map>).once('load', () => resolve()),
  );
  // Container may resize after init; keep the canvas in sync or it renders blank.
  resizeObserver = new ResizeObserver(() => {
    (map as InstanceType<typeof ml.Map> | null)?.resize();
  });
  resizeObserver.observe(mapEl.value);
  installLayers();
}

function installLayers() {
  if (!map || !MapLibreNS) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ml = MapLibreNS as any;
  const m = map as InstanceType<typeof ml.Map>;
  m.addSource('trip-legs', {
    type: 'geojson',
    data: buildGeoJson(visibleLegs.value),
  });
  m.addSource('trip-endpoints', {
    type: 'geojson',
    data: endpointFeatures(visibleLegs.value),
  });
  m.addLayer({
    id: 'trip-legs',
    type: 'line',
    source: 'trip-legs',
    paint: {
      'line-color': [
        'match',
        ['get', 'mode'],
        'plane',
        PLANE_COLOR,
        'train',
        TRAIN_COLOR,
        '#444',
      ],
      'line-width': [
        'interpolate',
        ['linear'],
        ['get', 'totalKgCo2eq'],
        0,
        1.5,
        100,
        2,
        1000,
        3,
        10000,
        5,
      ],
      'line-opacity': 0.85,
    },
  });
  m.addLayer({
    id: 'trip-endpoints',
    type: 'circle',
    source: 'trip-endpoints',
    paint: {
      'circle-radius': 3.5,
      'circle-color': '#212121',
      'circle-stroke-color': '#fff',
      'circle-stroke-width': 1.5,
    },
  });

  const popup = new ml.Popup({ closeButton: false, closeOnClick: false });
  m.on('mousemove', 'trip-legs', (e) => {
    m.getCanvas().style.cursor = 'pointer';
    const f = e.features?.[0];
    if (!f) return;
    const p = f.properties as {
      fromName: string;
      toName: string;
      tripCount: number;
      totalKgCo2eq: number;
    };
    const html =
      `<div style="font-size:12px"><strong>${escape(p.fromName)} ↔ ${escape(p.toName)}</strong><br/>` +
      `${t(`${MODULES.ProfessionalTravel}-trips-map-popup-trips`, { count: p.tripCount })} · ${escape(formatKgCo2eq(Number(p.totalKgCo2eq)))}</div>`;
    popup.setLngLat(e.lngLat).setHTML(html).addTo(m);
  });
  m.on('mouseleave', 'trip-legs', () => {
    m.getCanvas().style.cursor = '';
    popup.remove();
  });

  fitToLegs();
}

function fitToLegs() {
  if (!map || !MapLibreNS) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ml = MapLibreNS as any;
  const m = map as InstanceType<typeof ml.Map>;
  if (visibleLegs.value.length === 0) return;
  const bounds = new ml.LngLatBounds();
  for (const leg of visibleLegs.value) {
    bounds.extend(leg.from);
    bounds.extend(leg.to);
  }
  m.fitBounds(bounds, { padding: 32, maxZoom: 6, animate: false });
}

function escape(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

watch(
  () => visibleLegs.value,
  () => {
    if (!map || !MapLibreNS) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const m = map as any;
    const legsSrc = m.getSource('trip-legs');
    const endsSrc = m.getSource('trip-endpoints');
    if (legsSrc && 'setData' in legsSrc) {
      (legsSrc as { setData: (d: unknown) => void }).setData(
        buildGeoJson(visibleLegs.value),
      );
    }
    if (endsSrc && 'setData' in endsSrc) {
      (endsSrc as { setData: (d: unknown) => void }).setData(
        endpointFeatures(visibleLegs.value),
      );
    }
    fitToLegs();
  },
  { deep: true },
);

// Not gated on loading so a refetch swaps data in place instead of unmounting
// the canvas, which would orphan the maplibre instance.
const hasLegs = computed(() => visibleLegs.value.length > 0);

function destroyMap() {
  resizeObserver?.disconnect();
  resizeObserver = null;
  if (map && MapLibreNS) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (map as any).remove();
  }
  map = null;
}

onMounted(() => {
  if (hasLegs.value) void ensureMap();
});

// flush:'post': legs arrive after mount, so wait for the canvas to render.
// Rebuild from scratch whenever legs come and go.
watch(
  hasLegs,
  (has) => {
    if (has && !map) void ensureMap();
    else if (!has && map) destroyMap();
  },
  { flush: 'post' },
);

onBeforeUnmount(() => {
  destroyMap();
});
</script>

<style scoped lang="scss">
.trips-map {
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: 4px;
}

.trips-map__canvas {
  position: absolute;
  inset: 0;
}

.trips-map__sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
