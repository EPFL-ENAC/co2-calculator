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
      <div class="trips-map__legend" aria-hidden="true">
        <div class="trips-map__legend-block">
          <div class="trips-map__legend-caption">
            {{ t(`${MODULES.ProfessionalTravel}-trips-map-legend-emissions`) }}
          </div>
          <div
            class="trips-map__legend-gradient"
            :style="{ background: CO2_RAMP_CSS }"
          />
          <div class="trips-map__legend-scale">
            <span>0</span>
            <span>{{ formatKgCo2eq(niceMaxKg) }}</span>
          </div>
        </div>
        <div class="trips-map__legend-block">
          <div class="trips-map__legend-caption">
            {{ t(`${MODULES.ProfessionalTravel}-trips-map-legend-trips`) }}
          </div>
          <svg
            class="trips-map__legend-width"
            viewBox="0 0 120 12"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <polygon points="2,6.75 118,1 118,11" />
          </svg>
          <div class="trips-map__legend-scale">
            <span>1</span>
            <span>{{ niceMaxTrips }}</span>
          </div>
        </div>
        <div v-if="!modeFilter" class="trips-map__legend-modes">
          <span class="trips-map__legend-mode">
            <svg
              class="trips-map__legend-glyph"
              viewBox="0 0 20 10"
              aria-hidden="true"
            >
              <path d="M1 8 Q10 -2 19 8" />
            </svg>
            {{ t('plane') }}
          </span>
          <span class="trips-map__legend-mode">
            <svg
              class="trips-map__legend-glyph"
              viewBox="0 0 20 10"
              aria-hidden="true"
            >
              <line x1="1" y1="5" x2="19" y2="5" />
            </svg>
            {{ t('train') }}
          </span>
        </div>
      </div>
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
import type { TripLeg } from 'src/stores/modules';
import { formatKgCo2eq, niceCeil } from 'src/utils/number';
import {
  CO2_RAMP_CSS,
  LINE_COLOR_EXPR,
  aggregateLegs,
  buildEndpointFeatures,
  buildTripsGeoJson,
} from 'src/utils/trips-map';

const props = withDefaults(
  defineProps<{
    legs: TripLeg[];
    modeFilter?: 'plane' | 'train';
    height?: string;
    loading?: boolean;
    ariaLabel?: string;
    testid?: string;
  }>(),
  {
    height: '360px',
    loading: false,
    ariaLabel: 'Trips map',
    testid: 'trips-map',
    modeFilter: undefined,
  },
);

const { t } = useI18n();

const LINE_LAYERS = ['trip-legs-lines'];

const visibleLegs = computed(() => aggregateLegs(props.legs, props.modeFilter));

// Legend bounds rounded up to a tidy ceiling so the scale reads 0→500 rather
// than 0→459.
const niceMaxKg = computed(() =>
  niceCeil(visibleLegs.value.reduce((m, l) => Math.max(m, l.totalKgCo2eq), 0)),
);
const niceMaxTrips = computed(() =>
  niceCeil(visibleLegs.value.reduce((m, l) => Math.max(m, l.tripCount), 0)),
);

const mapEl = ref<HTMLDivElement | null>(null);
let map: unknown = null;
let MapLibreNS: unknown = null;
let resizeObserver: ResizeObserver | null = null;

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
          paint: {
            'raster-saturation': -1,
            'raster-brightness-min': 0.4,
            'raster-opacity': 0.9,
            'raster-contrast': -0.05,
          },
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
    data: buildTripsGeoJson(visibleLegs.value),
  });
  m.addSource('trip-endpoints', {
    type: 'geojson',
    data: buildEndpointFeatures(visibleLegs.value),
  });
  // One layer for both modes (shape distinguishes them); line-sort-key keeps
  // the heaviest emitters on top so they're never hidden.
  m.addLayer({
    id: 'trip-legs-lines',
    type: 'line',
    source: 'trip-legs',
    layout: {
      'line-cap': 'round',
      'line-join': 'round',
      'line-sort-key': ['get', 'totalKgCo2eq'],
    },
    paint: {
      'line-color': LINE_COLOR_EXPR,
      'line-width': ['get', 'lineWidth'],
      'line-opacity': 0.9,
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
  m.on('mousemove', LINE_LAYERS, (e) => {
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
  m.on('mouseleave', LINE_LAYERS, () => {
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
        buildTripsGeoJson(visibleLegs.value),
      );
    }
    if (endsSrc && 'setData' in endsSrc) {
      (endsSrc as { setData: (d: unknown) => void }).setData(
        buildEndpointFeatures(visibleLegs.value),
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

.trips-map__legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 1;
  padding: 6px 8px;
  font-size: 11px;
  line-height: 1.3;
  color: #212121;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  pointer-events: none;
}

.trips-map__legend-caption {
  margin-bottom: 3px;
  font-weight: 600;
}

.trips-map__legend-block + .trips-map__legend-block {
  margin-top: 6px;
}

.trips-map__legend-gradient {
  width: 120px;
  height: 8px;
  border-radius: 2px;
}

.trips-map__legend-width {
  display: block;
  width: 120px;
  height: 9px;
}

.trips-map__legend-width polygon {
  fill: #555;
}

.trips-map__legend-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
}

.trips-map__legend-modes {
  display: flex;
  gap: 10px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
}

.trips-map__legend-mode {
  display: flex;
  gap: 4px;
  align-items: center;
}

.trips-map__legend-glyph {
  width: 20px;
  height: 10px;
  overflow: visible;
}

.trips-map__legend-glyph path,
.trips-map__legend-glyph line {
  fill: none;
  stroke: #8c2981;
  stroke-width: 2;
  stroke-linecap: round;
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
