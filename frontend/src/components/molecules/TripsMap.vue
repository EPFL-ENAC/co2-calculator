<template>
  <div class="trips-map-block">
    <div
      class="trips-map"
      :style="{ height }"
      role="region"
      :aria-label="ariaLabel"
      :data-testid="testid"
    >
      <q-skeleton v-if="loading && !visibleLegs.length" :height="height" />
      <div
        v-else-if="!visibleLegs.length"
        class="column flex-center full-height text-center q-pa-md text-body2 text-secondary"
      >
        <q-icon :name="matMap" size="lg" class="text-grey-6 q-mb-sm" />
        {{ t(`${MODULES.ProfessionalTravel}-trips-map-empty`) }}
      </div>
      <template v-else>
        <div ref="mapEl" class="trips-map__canvas" />
        <div class="trips-map__legend">
          <div class="trips-map__legend-block" aria-hidden="true">
            <div class="trips-map__legend-caption">
              {{
                t(`${MODULES.ProfessionalTravel}-trips-map-legend-emissions`)
              }}
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
          <div class="trips-map__legend-block" aria-hidden="true">
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
          <!-- Selectable mode legend: the dashed-arc (plane) and straight-line
               (train) glyphs double as toggles. Deselected → dimmed. Shown only
               when both modes exist and no mode is pinned by the parent. -->
          <div
            v-if="showModeFilter"
            class="trips-map__legend-modes trips-map__legend-modes--toggle"
            role="group"
            :aria-label="
              t(`${MODULES.ProfessionalTravel}-trips-map-filter-mode-aria`)
            "
          >
            <button
              type="button"
              class="trips-map__legend-mode"
              :class="{
                'trips-map__legend-mode--off': !isModeSelected('plane'),
              }"
              :aria-pressed="isModeSelected('plane')"
              data-testid="trips-map-mode-plane"
              @click="toggleMode('plane')"
            >
              <q-icon
                :name="
                  isModeSelected('plane')
                    ? matCheckBox
                    : matCheckBoxOutlineBlank
                "
                :color="isModeSelected('plane') ? 'primary' : 'grey-7'"
                size="15px"
              />
              <svg
                class="trips-map__legend-glyph"
                viewBox="0 0 20 10"
                aria-hidden="true"
              >
                <path d="M1 8 Q10 -2 19 8" />
              </svg>
              {{ t('plane') }}
            </button>
            <button
              type="button"
              class="trips-map__legend-mode"
              :class="{
                'trips-map__legend-mode--off': !isModeSelected('train'),
              }"
              :aria-pressed="isModeSelected('train')"
              data-testid="trips-map-mode-train"
              @click="toggleMode('train')"
            >
              <q-icon
                :name="
                  isModeSelected('train')
                    ? matCheckBox
                    : matCheckBoxOutlineBlank
                "
                :color="isModeSelected('train') ? 'primary' : 'grey-7'"
                size="15px"
              />
              <svg
                class="trips-map__legend-glyph"
                viewBox="0 0 20 10"
                aria-hidden="true"
              >
                <line x1="1" y1="5" x2="19" y2="5" />
              </svg>
              {{ t('train') }}
            </button>
          </div>
          <!-- Static legend when there's nothing to toggle (single-mode data). -->
          <div
            v-else-if="!modeFilter"
            class="trips-map__legend-modes"
            aria-hidden="true"
          >
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

    <!-- Member filter under the map: manager-only (the API only returns >1
         traveler for a principal/global). -->
    <div
      v-if="travelers.length >= 2"
      class="trips-map__members q-mt-md"
      role="group"
      :aria-label="
        t(`${MODULES.ProfessionalTravel}-trips-map-filter-members-aria`)
      "
      data-testid="trips-map-member-filter"
    >
      <div class="row items-center q-mb-xs">
        <span class="text-grey-8 text-weight-medium">
          {{
            t(`${MODULES.ProfessionalTravel}-trips-map-filter-members-title`)
          }}
        </span>
        <span class="trips-map__members-count q-ml-xs">
          {{
            t(`${MODULES.ProfessionalTravel}-trips-map-filter-members-label`, {
              shown: shownTravelerCount,
              total: travelers.length,
            })
          }}
        </span>
        <q-space />
        <button
          type="button"
          class="trips-map__members-action"
          @click="selectAllTravelers"
        >
          {{ t(`${MODULES.ProfessionalTravel}-trips-map-filter-all`) }}
        </button>
        <span class="trips-map__members-sep">·</span>
        <button
          type="button"
          class="trips-map__members-action"
          @click="selectNoTravelers"
        >
          {{ t(`${MODULES.ProfessionalTravel}-trips-map-filter-none`) }}
        </button>
      </div>
      <div class="trips-map__member-list">
        <button
          v-for="tr in travelers"
          :key="tr.id"
          type="button"
          class="trips-map__member"
          :class="{ 'trips-map__member--off': !isTravelerSelected(tr.id) }"
          :aria-pressed="isTravelerSelected(tr.id)"
          @click="toggleTraveler(tr.id)"
          @mouseenter="hoveredTravelerId = tr.id"
          @mouseleave="hoveredTravelerId = null"
          @focus="hoveredTravelerId = tr.id"
          @blur="hoveredTravelerId = null"
        >
          <q-icon
            :name="
              isTravelerSelected(tr.id)
                ? matCheckCircle
                : matRadioButtonUnchecked
            "
            :color="isTravelerSelected(tr.id) ? 'primary' : 'grey-5'"
            size="13px"
          />
          <span class="trips-map__member-name">{{ tr.name }}</span>
          <span class="trips-map__member-value">{{
            formatKgCo2eq(tr.totalKgCo2eq)
          }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  matCheckBox,
  matCheckBoxOutlineBlank,
  matCheckCircle,
  matMap,
  matRadioButtonUnchecked,
} from '@quasar/extras/material-icons';
import { useI18n } from 'vue-i18n';
import { MODULES } from 'src/constant/modules';
import type { TripLeg } from 'src/stores/modules';
import { formatKgCo2eq, niceCeil } from 'src/utils/number';
import {
  CO2_RAMP_CSS,
  LINE_COLOR_EXPR,
  aggregateLegs,
  buildEndpointFeatures,
  buildLegPopupHtml,
  buildTripsGeoJson,
  travelerTotals,
  travelerRouteKeys,
  legsToRender,
  toggleTravelerSelection,
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

const LINE_LAYERS = ['trip-legs-lines-train', 'trip-legs-lines-plane'];

// Vector basemap (OpenFreeMap Positron): city labels, minimal land, no green.
// Its seas are recoloured to the Professional Travel chart blue
// (babyBlue.darker, #A2CBED) so the map reads as part of that section.
const BASEMAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';
const SEA_COLOR = '#A2CBED';
// Grey for routes dimmed during a member hover.
const DIM_COLOR = '#b8b8b8';

// Mode filter: a multi-select of plane / train. Both selected (the default) =
// both shown; deselect one to focus the other. We never allow zero — the toggle
// lives in the map legend, which is hidden when nothing is shown, so keeping at
// least one mode avoids a dead-end. A parent-pinned `modeFilter` overrides this
// and hides the toggle.
const selectedModes = ref<Set<'plane' | 'train'>>(new Set(['plane', 'train']));

// Only offer the toggle on the overall map and only when both modes are present
// — filtering to a mode that has no trips would just blank the map.
const showModeFilter = computed(
  () =>
    props.modeFilter === undefined &&
    props.legs.some((l) => l.mode === 'plane') &&
    props.legs.some((l) => l.mode === 'train'),
);

function isModeSelected(mode: 'plane' | 'train'): boolean {
  return selectedModes.value.has(mode);
}

function toggleMode(mode: 'plane' | 'train') {
  const next = new Set(selectedModes.value);
  if (next.has(mode)) {
    if (next.size === 1) return; // keep at least one mode visible
    next.delete(mode);
  } else {
    next.add(mode);
  }
  selectedModes.value = next;
}

// Modes actually rendered. Pinned prop wins; otherwise the legend multi-select
// when it's offered, else both (single-mode data has nothing to filter).
const visibleModes = computed<Set<'plane' | 'train'>>(() => {
  if (props.modeFilter) return new Set([props.modeFilter]);
  if (!showModeFilter.value) return new Set(['plane', 'train']);
  return selectedModes.value;
});

// Distinct travelers with per-person emission totals (only >1 for managers).
const travelers = computed(() => travelerTotals(props.legs));

// null = all travelers shown (default). A Set narrows to a chosen subset.
const selectedTravelerIds = ref<Set<string> | null>(null);

function isTravelerSelected(id: string): boolean {
  return (
    selectedTravelerIds.value === null || selectedTravelerIds.value.has(id)
  );
}

const shownTravelerCount = computed(() =>
  selectedTravelerIds.value === null
    ? travelers.value.length
    : selectedTravelerIds.value.size,
);

function toggleTraveler(id: string) {
  selectedTravelerIds.value = toggleTravelerSelection(
    selectedTravelerIds.value,
    id,
    travelers.value.map((tr) => tr.id),
  );
}

function selectAllTravelers() {
  selectedTravelerIds.value = null;
}

function selectNoTravelers() {
  selectedTravelerIds.value = new Set();
}

// Hovering a member spotlights their routes: theirs stay in colour, every
// other rendered route is dimmed. `null` = no hover.
const hoveredTravelerId = ref<string | null>(null);
const highlightKeys = computed(() =>
  hoveredTravelerId.value === null
    ? null
    : travelerRouteKeys(props.legs, hoveredTravelerId.value),
);

// What the map renders: the selected set, plus the hovered member's legs (so a
// deselected member's trips are revealed on hover). Their routes are then
// spotlighted via highlightKeys, the rest dimmed.
const visibleLegs = computed(() => {
  const rendered = legsToRender(
    props.legs,
    selectedTravelerIds.value,
    hoveredTravelerId.value,
  );
  const modes = visibleModes.value;
  return aggregateLegs(rendered.filter((l) => modes.has(l.mode)));
});

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
    style: BASEMAP_STYLE_URL,
    center: [6.6323, 46.5197],
    zoom: 3,
    // Compact (ⓘ) attribution; the style's sources already credit
    // OpenMapTiles + OpenStreetMap, we add the OpenFreeMap host credit.
    attributionControl: {
      compact: true,
      customAttribution: '© OpenFreeMap',
    },
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
  // MapLibre renders the compact attribution expanded on first load; collapse
  // it to just the ⓘ so it doesn't overlay the map until the user opens it.
  const attrib = mapEl.value.querySelector('.maplibregl-ctrl-attrib');
  attrib?.removeAttribute('open');
  attrib?.classList.remove('maplibregl-compact-show');
  installLayers();
}

// Recolour the basemap's water fill layers to the Professional Travel chart
// blue. Matches both ocean fills and inland-water fills by source-layer/id.
function recolorSeas() {
  if (!map || !MapLibreNS) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const m = map as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  for (const layer of (m.getStyle()?.layers ?? []) as any[]) {
    const name = `${layer['source-layer'] ?? ''} ${layer.id}`.toLowerCase();
    // Seas are plain `fill` layers in this basemap (never fill-extrusion), so
    // only the fill-* paint properties apply here.
    if (
      layer.type === 'fill' &&
      /water|ocean|sea|bathymetr|marine/.test(name)
    ) {
      m.setPaintProperty(layer.id, 'fill-color', SEA_COLOR);
      m.setPaintProperty(layer.id, 'fill-opacity', 1);
    }
  }
}

function installLayers() {
  if (!map || !MapLibreNS) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ml = MapLibreNS as any;
  const m = map as InstanceType<typeof ml.Map>;
  recolorSeas();
  m.addSource('trip-legs', {
    type: 'geojson',
    data: buildTripsGeoJson(visibleLegs.value, highlightKeys.value),
  });
  m.addSource('trip-endpoints', {
    type: 'geojson',
    data: buildEndpointFeatures(visibleLegs.value),
  });
  // One layer per mode: trains solid, planes dashed — so the two modes read
  // clearly even where curvature alone is ambiguous. line-sort-key keeps the
  // heaviest emitters on top; dimmed (non-hovered) routes sort below so the
  // spotlighted ones stay readable.
  const lineLayout = {
    'line-cap': 'round' as const,
    'line-join': 'round' as const,
    'line-sort-key': [
      'case',
      ['==', ['get', 'dim'], 1],
      -1,
      ['get', 'totalKgCo2eq'],
    ],
  };
  // dim=1 (member hover, not this route) → flat grey, low opacity; otherwise
  // the emissions ramp at full strength.
  const linePaint = {
    'line-color': [
      'case',
      ['==', ['get', 'dim'], 1],
      DIM_COLOR,
      LINE_COLOR_EXPR,
    ],
    'line-width': ['get', 'lineWidth'],
    'line-opacity': ['case', ['==', ['get', 'dim'], 1], 0.18, 0.9],
  };
  m.addLayer({
    id: 'trip-legs-lines-train',
    type: 'line',
    source: 'trip-legs',
    filter: ['==', ['get', 'mode'], 'train'],
    layout: lineLayout,
    paint: linePaint,
  });
  // Planes reuse the train stroke, plus a dash.
  m.addLayer({
    id: 'trip-legs-lines-plane',
    type: 'line',
    source: 'trip-legs',
    filter: ['==', ['get', 'mode'], 'plane'],
    layout: lineLayout,
    paint: { ...linePaint, 'line-dasharray': [2, 1.5] },
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

  const popup = new ml.Popup({
    closeButton: false,
    closeOnClick: false,
    offset: 12,
  });
  m.on('mousemove', LINE_LAYERS, (e) => {
    m.getCanvas().style.cursor = 'pointer';
    const f = e.features?.[0];
    if (!f) return;
    popup
      .setLngLat(e.lngLat)
      .setHTML(buildLegPopupHtml(f.properties, t))
      .addTo(m);
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

// Push the current legs GeoJSON (with hover dimming baked in) to the source.
function refreshLegsSource() {
  if (!map || !MapLibreNS) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const legsSrc = (map as any).getSource('trip-legs');
  if (legsSrc && 'setData' in legsSrc) {
    (legsSrc as { setData: (d: unknown) => void }).setData(
      buildTripsGeoJson(visibleLegs.value, highlightKeys.value),
    );
  }
}

watch(
  () => visibleLegs.value,
  () => {
    if (!map || !MapLibreNS) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const endsSrc = (map as any).getSource('trip-endpoints');
    refreshLegsSource();
    if (endsSrc && 'setData' in endsSrc) {
      (endsSrc as { setData: (d: unknown) => void }).setData(
        buildEndpointFeatures(visibleLegs.value),
      );
    }
  },
  { deep: true },
);

// Hover only restyles the existing lines — no refit, no endpoint rebuild.
watch(highlightKeys, refreshLegsSource);

// Refit only when the *selection* (or data/mode) changes — never on hover, so
// revealing a hovered member's trips doesn't yank the viewport around. None of
// these deps change on hover (props.legs is the same array; the selection ref
// is untouched).
watch(
  [
    selectedTravelerIds,
    selectedModes,
    () => props.modeFilter,
    () => props.legs,
  ],
  () => fitToLegs(),
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

// Member filter sits in normal flow below the map (not an overlay), so a
// long roster wraps and pushes the card height rather than covering the map.
.trips-map__members {
  font-size: 12px;
}

.trips-map__members-count {
  color: #9e9e9e;
}

// "All / None" as quiet text links rather than buttons.
.trips-map__members-action {
  padding: 0;
  font: inherit;
  color: #707070;
  cursor: pointer;
  background: none;
  border: 0;

  &:hover {
    color: #212121;
    text-decoration: underline;
  }
}

.trips-map__members-sep {
  margin: 0 4px;
  color: #cfcfcf;
}

.trips-map__member-list {
  display: flex;
  flex-wrap: wrap;
  gap: 1px 2px;
}

// Each member is a borderless, background-free toggle: a small leading icon
// carries the selected/unselected state. Hovering tints the row and spotlights
// that person's trips on the map.
.trips-map__member {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  font: inherit;
  line-height: 1.4;
  color: #212121;
  cursor: pointer;
  background: none;
  border: 0;
  border-radius: 4px;

  &:hover {
    background: rgba(0, 0, 0, 0.05);
  }
}

.trips-map__member--off {
  color: #9e9e9e;
}

.trips-map__member-value {
  font-size: 0.85em;
  opacity: 0.65;
}

.trips-map__legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 1;
  // Floor the width so the scales stay a sensible size; the mode toggles can
  // push it wider, and the scale bars stretch to fill (width: 100% below).
  min-width: 140px;
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
  width: 100%;
  height: 8px;
  border-radius: 2px;
}

.trips-map__legend-width {
  display: block;
  width: 100%;
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

// The legend is pointer-events:none so it never intercepts map drags; the mode
// toggles re-enable them just on themselves.
.trips-map__legend-modes--toggle {
  pointer-events: auto;
}

.trips-map__legend-mode {
  display: flex;
  gap: 4px;
  align-items: center;
}

// Glyph rows double as toggle buttons: a leading checkbox + a hover background
// make them read as clickable. Deselected stays legible (muted, not disabled)
// so it clearly invites a click.
button.trips-map__legend-mode {
  padding: 1px 5px 1px 3px;
  font: inherit;
  color: #212121;
  cursor: pointer;
  background: none;
  border: 0;
  border-radius: 4px;
}

button.trips-map__legend-mode:hover {
  background: rgba(0, 0, 0, 0.06);
}

.trips-map__legend-mode--off {
  color: #8e8e8e;
}

.trips-map__legend-mode--off .trips-map__legend-glyph path,
.trips-map__legend-mode--off .trips-map__legend-glyph line {
  stroke: #bbb;
}

.trips-map__legend-glyph {
  width: 20px;
  height: 10px;
  overflow: visible;
}

.trips-map__legend-glyph path,
.trips-map__legend-glyph line {
  fill: none;
  stroke: #555;
  stroke-width: 2;
  stroke-linecap: round;
}

// The plane glyph (curved <path>) is dashed to match the dashed plane arcs on
// the map; the train glyph (straight <line>) stays solid. Butt caps + wider
// gaps so the dashes read clearly at this small size (legend only — the map
// keeps its own line-dasharray).
.trips-map__legend-glyph path {
  stroke-dasharray: 3 3;
  stroke-linecap: butt;
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
