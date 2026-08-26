/**
 * Stateful HTTP-boundary fake backend for the simulator Explorer suite
 * (issue #1793).
 *
 * ``__LIGHTHOUSE_BYPASS__`` is NOT set: ``validateUnitGuard`` returns early
 * when it sees the flag and never sets ``selectedUnit`` / ``selectedYear``,
 * which ``SimulationExplorePage`` dereferences in ``onMounted``.  Instead the
 * real guards run against a mocked API surface.
 *
 * Every module/submodule list lives in an in-memory store keyed by
 * ``{reportId}/{module}/{submodule}``.  POST appends (with a deterministic
 * fake kg CO₂-eq), GET lists, ``?preview_limit=0`` derives the counts, so
 * the page behaves like a real backend without one.  The same handlers serve
 * the calculator report (42) and the explorer report (99), which lets a spec
 * render the calculator module page under identical data to compare forms.
 *
 * CSV import: ``files/temp-upload`` parses the multipart CSV body, and
 * ``sync/dispatch`` inserts those rows into the targeted submodule.  The SSE
 * job stream is a ``window.EventSource`` shim (``installExplorerInitScripts``)
 * that reports the job FINISHED/SUCCESS on the next tick.
 *
 * Routes are registered on the browser context so pages the app opens
 * itself (the print report) are served too.  Playwright evaluates route
 * handlers LIFO: the catch-all is registered FIRST (lowest priority),
 * specific routes LAST.
 */

import type { BrowserContext, Page, Request, Route } from '@playwright/test';

export const UNIT_ID = 10;
export const YEAR = 2024;
export const CALCULATOR_REPORT_ID = 42;
export const EXPLORER_REPORT_ID = 99;
export const SIMULATOR_URL = `/en/${UNIT_ID}/${YEAR}/simulation/explore/sim-1`;
export const calculatorModuleUrl = (module: string) =>
  `/en/${UNIT_ID}/${YEAR}/${module}`;

export type MockRole = 'principal' | 'std';

const ALL_MODULE_PERMISSIONS = {
  'modules.headcount': ['view', 'edit'],
  'modules.professional_travel': ['view', 'edit'],
  'modules.process_emissions': ['view', 'edit'],
  'modules.buildings': ['view', 'edit'],
  'modules.equipment': ['view', 'edit'],
  'modules.purchase': ['view', 'edit'],
  'modules.research_facilities': ['view', 'edit'],
  'modules.external_cloud_and_ai': ['view', 'edit'],
};

function buildUser(role: MockRole) {
  return {
    id: 1,
    email: 'test@example.com',
    display_name: role === 'principal' ? 'Principal User' : 'Standard User',
    institutional_id: 'test-user',
    roles_raw: [`calco2.user.${role}`],
    permissions:
      role === 'principal'
        ? { ...ALL_MODULE_PERMISSIONS, 'module.status': ['view', 'edit'] }
        : { ...ALL_MODULE_PERMISSIONS },
  };
}

const MOCK_UNIT = {
  id: UNIT_ID,
  name: String(UNIT_ID),
  institutional_id: 'unit-10',
  principal_user_id: 'user-1',
  principal_user_function: 'Test',
  principal_user_name: 'Test User',
  affiliations: [],
  current_user_role: 'principal',
};

const MOCK_CARBON_REPORT = {
  id: CALCULATOR_REPORT_ID,
  unit_id: UNIT_ID,
  year: YEAR,
  carbon_project_id: 1,
};

const MOCK_SIMULATOR_REPORT = {
  id: EXPLORER_REPORT_ID,
  unit_id: UNIT_ID,
  year: YEAR,
  carbon_project_id: 2,
};

// ─── Module / submodule registry ─────────────────────────────────────────────

interface SubDef {
  module: string;
  sub: string;
  enumId: number;
}

export const SUBMODULES: SubDef[] = [
  { module: 'headcount', sub: 'planner_headcount', enumId: 80 },
  { module: 'headcount', sub: 'member', enumId: 1 },
  { module: 'headcount', sub: 'student', enumId: 2 },
  { module: 'process-emissions', sub: 'process_emissions', enumId: 50 },
  { module: 'buildings', sub: 'energy_combustion', enumId: 31 },
  { module: 'buildings', sub: 'building', enumId: 30 },
  { module: 'equipment', sub: 'scientific', enumId: 10 },
  { module: 'equipment', sub: 'it', enumId: 11 },
  { module: 'equipment', sub: 'other', enumId: 12 },
  { module: 'external-cloud-and-ai', sub: 'external_clouds', enumId: 40 },
  { module: 'external-cloud-and-ai', sub: 'external_ai', enumId: 41 },
  { module: 'professional-travel', sub: 'plane', enumId: 20 },
  { module: 'professional-travel', sub: 'train', enumId: 21 },
  { module: 'purchase', sub: 'scientific_equipment', enumId: 60 },
  { module: 'purchase', sub: 'it_equipment', enumId: 61 },
  { module: 'purchase', sub: 'consumable_accessories', enumId: 62 },
  {
    module: 'purchase',
    sub: 'biological_chemical_gaseous_product',
    enumId: 63,
  },
  { module: 'purchase', sub: 'services', enumId: 64 },
  { module: 'purchase', sub: 'vehicles', enumId: 65 },
  { module: 'purchase', sub: 'other_purchases', enumId: 66 },
  { module: 'purchase', sub: 'purchases_centralized', enumId: 67 },
  { module: 'research-facilities', sub: 'research-facilities', enumId: 70 },
  { module: 'research-facilities', sub: 'animal_facilities', enumId: 71 },
];

const MODULE_TYPE_IDS: Record<string, number> = {
  headcount: 1,
  'professional-travel': 2,
  buildings: 3,
  equipment: 4,
  purchase: 5,
  'research-facilities': 6,
  'external-cloud-and-ai': 7,
  'process-emissions': 8,
};

// ─── Factor catalogue (class → subclasses), keyed by enumSubmodule id ─────────

export const FACTOR_CLASS_MAP: Record<number, Record<string, string[]>> = {
  50: { co2: ['fossil'], ch4: ['biogenic'], sf6: ['electrical'] },
  31: { natural_gas: [], heating_oil: [], pellets: [] },
  30: { BC: [], GC: [] },
  10: { Centrifuge: ['Benchtop', 'Floor'], Microscope: ['Optical'] },
  11: { Laptop: [], Monitor: [] },
  12: { Freezer: ['-80 °C'], Fridge: ['Standard'] },
  40: { AWS: ['virtualisation', 'stockage'], Azure: ['calcul'] },
  41: { OpenAI: ['chat'], Anthropic: ['chat'] },
  60: { 'Laboratory equipment': [] },
  61: { Computers: [] },
  62: { 'Lab consumables': [] },
  63: { Solvents: [] },
  64: { Consulting: [] },
  65: { Cars: [] },
  66: { Furniture: [] },
  67: { LN2: [] },
};

const FACTOR_VALUES: Record<number, Record<string, unknown>> = {
  31: { unit: 'kWh' },
  30: {
    heating_kwh_per_square_meter: 50,
    cooling_kwh_per_square_meter: 10,
    ventilation_kwh_per_square_meter: 20,
    lighting_kwh_per_square_meter: 15,
  },
  10: { active_power_w: 500, standby_power_w: 50 },
  11: { active_power_w: 100, standby_power_w: 10 },
  12: { active_power_w: 300, standby_power_w: 30 },
  67: { unit: 'kg' },
};

export const BUILDING_ROOMS: Record<
  string,
  { room_name: string; room_type: string; room_surface_square_meter: number }[]
> = {
  BC: [
    { room_name: 'BC 101', room_type: 'office', room_surface_square_meter: 20 },
    {
      room_name: 'BC 210',
      room_type: 'laboratories',
      room_surface_square_meter: 60,
    },
  ],
  GC: [
    { room_name: 'GC A1', room_type: 'office', room_surface_square_meter: 30 },
  ],
};

export const LOCATIONS = [
  {
    id: 1,
    name: 'Geneva',
    iata_code: 'GVA',
    country_code: 'CH',
    natural_key: 'geneva',
  },
  {
    id: 2,
    name: 'Paris',
    iata_code: 'CDG',
    country_code: 'FR',
    natural_key: 'paris',
  },
  {
    id: 3,
    name: 'London',
    iata_code: 'LHR',
    country_code: 'GB',
    natural_key: 'london',
  },
  {
    id: 4,
    name: 'Lausanne',
    iata_code: null,
    country_code: 'CH',
    natural_key: 'lausanne',
  },
  {
    id: 5,
    name: 'Zurich',
    iata_code: 'ZRH',
    country_code: 'CH',
    natural_key: 'zurich',
  },
];

function findLocation(
  row: Record<string, unknown>,
  side: 'origin' | 'destination',
) {
  return LOCATIONS.find(
    (l) =>
      l.id === Number(row[`${side}_location_id`]) ||
      (row[`${side}_iata`] != null && l.iata_code === row[`${side}_iata`]) ||
      (row[`${side}_natural_key`] != null &&
        l.natural_key === row[`${side}_natural_key`]) ||
      (row[`${side}_name`] != null &&
        row[`${side}_name`] !== '' &&
        l.name === row[`${side}_name`]),
  );
}

export function distanceBetween(a: number, b: number): number {
  return Math.abs(a - b) * 400;
}

// ─── Deterministic fake emission formulas ─────────────────────────────────────

const GWP: Record<string, number> = { co2: 1, ch4: 28, n2o: 265, sf6: 23500 };
const COMBUSTION_EF: Record<string, number> = {
  natural_gas: 0.2,
  heating_oil: 0.3,
  pellets: 0.05,
};
const TRAVEL_EF: Record<string, number> = {
  business: 0.5,
  economy: 0.2,
  first: 0.02,
  second: 0.01,
};
const AI_EF: Record<string, number> = {
  '1_5': 10,
  '5_20': 40,
  '20_100': 150,
  gt_100: 500,
};

const num = (v: unknown): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

export function fakeKgCo2eq(sub: string, row: Record<string, unknown>): number {
  switch (sub) {
    case 'process_emissions':
      return num(row.quantity_kg) * (GWP[String(row.category)] ?? 1);
    case 'energy_combustion':
      return num(row.quantity) * (COMBUSTION_EF[String(row.name)] ?? 0.1);
    case 'building': {
      const kwh =
        num(row.heating_kwh_per_square_meter) +
        num(row.cooling_kwh_per_square_meter) +
        num(row.ventilation_kwh_per_square_meter) +
        num(row.lighting_kwh_per_square_meter);
      return (
        num(row.room_surface_square_meter) *
        (row.room_allocation_ratio == null
          ? 1
          : num(row.room_allocation_ratio)) *
        kwh *
        0.1
      );
    }
    case 'scientific':
    case 'it':
    case 'other': {
      const wh =
        num(row.active_usage_hours_per_week) * num(row.active_power_w) +
        num(row.standby_usage_hours_per_week) * num(row.standby_power_w);
      return (wh * 52) / 1000;
    }
    case 'external_clouds':
      return num(row.spent_amount) * 0.5;
    case 'external_ai':
      return (
        num(row.fte_count) * (AI_EF[String(row.requests_per_user_per_day)] ?? 1)
      );
    case 'plane':
    case 'train':
      return (
        num(row.distance_km) *
        num(row.number_of_trips) *
        (TRAVEL_EF[String(row.cabin_class)] ?? 0.1)
      );
    case 'purchases_centralized':
      return (
        num(row.annual_consumption) *
        (row.coef_to_kg == null ? 1 : num(row.coef_to_kg)) *
        2
      );
    default:
      return num(row.total_spent_amount) * 0.4;
  }
}

// ─── Report stats (chart input) ──────────────────────────────────────────────

export const REPORT_STATS = {
  buckets: {
    process_emissions: {
      scope: 1,
      additional: false,
      total_kg: 1200,
      by_emission_type: { '70200': 1200 },
    },
    buildings_energy_combustion: {
      scope: 1,
      additional: false,
      total_kg: 800,
      by_emission_type: { '60201': 800 },
    },
    buildings_room: {
      scope: 2,
      additional: false,
      total_kg: 2500,
      by_emission_type: { '6010101': 1500, '6010102': 1000 },
    },
    equipment: {
      scope: 2,
      additional: false,
      total_kg: 3000,
      by_emission_type: { '80100': 2000, '80200': 700, '80300': 300 },
    },
    external_cloud_and_ai: {
      scope: 3,
      additional: false,
      total_kg: 400,
      by_emission_type: { '110101': 250, '110204': 150 },
    },
    professional_travel: {
      scope: 3,
      additional: false,
      total_kg: 5000,
      by_emission_type: { '50102': 1000, '50203': 4000 },
    },
    purchases: {
      scope: 3,
      additional: false,
      total_kg: 6000,
      by_emission_type: { '90200': 4000, '90300': 2000 },
    },
    research_facilities: {
      scope: 3,
      additional: false,
      total_kg: 900,
      by_emission_type: { '100100': 900 },
    },
    commuting: {
      scope: 3,
      additional: true,
      total_kg: 1100,
      by_emission_type: { '30005': 1100 },
    },
    food: {
      scope: 3,
      additional: true,
      total_kg: 1300,
      by_emission_type: { '10001': 500, '10002': 800 },
    },
    waste: {
      scope: 3,
      additional: true,
      total_kg: 700,
      by_emission_type: { '20001': 700 },
    },
    embodied_energy: {
      scope: 3,
      additional: true,
      total_kg: 2000,
      by_emission_type: { '60300': 2000 },
      by_category: [],
      by_building: [],
    },
  },
  per_fte: {},
  quantities: {},
  validated_buckets: [
    'process_emissions',
    'buildings_energy_combustion',
    'buildings_room',
    'equipment',
    'external_cloud_and_ai',
    'professional_travel',
    'purchases',
    'research_facilities',
    'commuting',
    'food',
    'waste',
    'embodied_energy',
  ],
  total: 24900,
  validated_total: 24900,
  total_fte: 10,
  total_tonnes_validated_co2eq: 24.9,
  it: {
    total_kg: 3100,
    percentage_of_total: 12.4,
    per_fte: 310,
    percentage_of_source_modules: 20,
    categories: {
      equipment_it: 700,
      purchases_it: 2000,
      external_cloud_and_ai: 400,
      research_facilities_it: 0,
    },
    cloud_ai_detail: {},
    validated_sources: [],
    top_class_detail: {},
  },
};

/**
 * Back-office year configuration: every module enabled, CSV import switched
 * off for Centralized purchases (data_entry_type 67) only.
 */
export const YEAR_CONFIG = {
  year: YEAR,
  is_started: true,
  configuration_completed: '2024-01-01T00:00:00Z',
  config: {
    modules: Object.fromEntries(
      Object.values(MODULE_TYPE_IDS).map((id) => [
        String(id),
        {
          enabled: true,
          uncertainty_tag: 'medium',
          submodules:
            id === 5
              ? {
                  '67': {
                    enabled: true,
                    threshold: null,
                    csv_deactivated: true,
                  },
                }
              : {},
        },
      ]),
    ),
    reduction_objectives: {},
  },
};

/** Main-category total (tonnes) the Explorer BigNumber and chart show. */
export const MAIN_TOTAL_TONNES = 19.8;

// ─── CSV parsing (multipart body → rows) ─────────────────────────────────────

function parseCsv(text: string): Record<string, string>[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const cells = line.split(',').map((c) => c.trim());
    const row: Record<string, string> = {};
    headers.forEach((h, i) => {
      row[h] = cells[i] ?? '';
    });
    return row;
  });
}

function extractCsvFromMultipart(body: string): string {
  const parts = body.split(/--[^\r\n]+\r?\n/);
  for (const part of parts) {
    const idx = part.indexOf('\r\n\r\n');
    const idx2 = idx >= 0 ? idx : part.indexOf('\n\n');
    if (idx2 < 0) continue;
    const headers = part.slice(0, idx2);
    if (!/filename=/.test(headers)) continue;
    return part
      .slice(idx2)
      .trim()
      .replace(/\r?\n--.*$/s, '');
  }
  return '';
}

// ─── Fake backend ────────────────────────────────────────────────────────────

export interface LoggedRequest {
  method: string;
  url: string;
  body?: string;
}

export interface FakeBackend {
  requests: LoggedRequest[];
  /** Rows currently stored for a submodule of a report. */
  rows(
    reportId: number,
    module: string,
    sub: string,
  ): Record<string, unknown>[];
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function parseJsonBody(req: Request): Record<string, unknown> {
  try {
    return JSON.parse(req.postData() ?? '{}');
  } catch {
    return {};
  }
}

// Shared shape for a module's ?preview_limit=0 totals response.
function buildModuleTotalsResponse(
  module: string,
  totals: Record<number, number>,
) {
  return {
    module_type: module,
    unit: UNIT_ID,
    year: String(YEAR),
    data_entry_types_total_items: totals,
    carbon_report_module_id: 100 + (MODULE_TYPE_IDS[module] ?? 0),
    retrieved_at: '2024-01-01T00:00:00Z',
    submodules: {},
    totals: { total_submodules: 0, total_items: 0 },
  };
}

export async function installExplorerInitScripts(
  context: BrowserContext,
): Promise<void> {
  await context.addInitScript(() => {
    try {
      localStorage.clear();
    } catch {
      // ignore
    }
    class FakeEventSource extends EventTarget {
      url: string;
      readyState = 1;
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      onopen: ((ev: Event) => void) | null = null;
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSED = 2;
      constructor(url: string) {
        super();
        this.url = url;
        const match = url.match(/\/sync\/jobs\/([^/]+)\/stream/);
        if (match) {
          const jobId = Number(match[1]);
          setTimeout(() => {
            if (this.readyState !== 1) return;
            const payload = {
              job_id: jobId,
              year: 2024,
              state: 3,
              result: 0,
              status_message: 'done',
              meta: {},
            };
            this.onmessage?.(
              new MessageEvent('message', { data: JSON.stringify(payload) }),
            );
          }, 50);
        }
      }
      close() {
        this.readyState = 2;
      }
    }
    (window as unknown as { EventSource: unknown }).EventSource =
      FakeEventSource;
  });
}

export async function mockExplorerBackend(
  page: Page,
  options: { role?: MockRole } = {},
): Promise<FakeBackend> {
  const role = options.role ?? 'principal';
  const requests: LoggedRequest[] = [];
  const store = new Map<string, Record<string, unknown>[]>();
  let nextId = 1;
  let exploreReportCreated = false;
  let pendingCsvRows: Record<string, string>[] = [];

  const key = (reportId: number, module: string, sub: string) =>
    `${reportId}/${module}/${sub}`;
  const rowsOf = (reportId: number, module: string, sub: string) => {
    const k = key(reportId, module, sub);
    if (!store.has(k)) store.set(k, []);
    return store.get(k)!;
  };
  const insert = (
    reportId: number,
    module: string,
    sub: string,
    payload: Record<string, unknown>,
  ) => {
    const row: Record<string, unknown> = { ...payload, id: nextId++ };
    if (sub === 'plane' || sub === 'train') {
      const origin = findLocation(row, 'origin');
      const dest = findLocation(row, 'destination');
      row.origin_name = origin?.name ?? row.origin_name ?? '';
      row.destination_name = dest?.name ?? row.destination_name ?? '';
      row.origin_iata = origin?.iata_code ?? null;
      row.destination_iata = dest?.iata_code ?? null;
      if (origin && dest) {
        row.distance_km = distanceBetween(origin.id, dest.id);
      }
      row.traveler_name = null;
    }
    if (sub !== 'planner_headcount' && !row.kg_co2eq) {
      row.kg_co2eq = fakeKgCo2eq(sub, row);
    }
    rowsOf(reportId, module, sub).push(row);
    return row;
  };

  const context = page.context();
  context.on('request', (req) => {
    if (req.url().includes('/api/v1/')) {
      requests.push({
        method: req.method(),
        url: req.url(),
        body: req.postData() ?? undefined,
      });
    }
  });

  // ─── Catch-all (lowest priority) ───────────────────────────────────────────
  await context.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, body: '' }),
  );

  // ─── Taxonomy / factors ────────────────────────────────────────────────────
  await context.route('**/api/v1/taxonomies/**', (route) =>
    json(route, { name: '', label: '', children: [] }),
  );

  await context.route(
    /.*\/api\/v1\/factors\/(\d+)\/class-subclass-map/,
    (route) => {
      const id = Number(
        route
          .request()
          .url()
          .match(/factors\/(\d+)\//)![1],
      );
      return json(route, FACTOR_CLASS_MAP[id] ?? {});
    },
  );

  await context.route(/.*\/api\/v1\/factors\/(\d+)\/classes\//, (route) => {
    const id = Number(
      route
        .request()
        .url()
        .match(/factors\/(\d+)\//)![1],
    );
    const values = FACTOR_VALUES[id];
    return values
      ? json(route, values)
      : route.fulfill({ status: 404, body: '' });
  });

  await context.route(/.*\/api\/v1\/factors\/7[01]\/list/, (route) =>
    json(route, []),
  );

  await context.route(/.*\/api\/v1\/modules\/building-rooms/, (route) => {
    const url = new URL(route.request().url());
    const building = url.searchParams.get('building_name');
    if (!building) {
      return json(
        route,
        Object.keys(BUILDING_ROOMS).map((b) => ({
          building_name: b,
          building_location: 'Lausanne',
        })),
      );
    }
    return json(
      route,
      (BUILDING_ROOMS[building] ?? []).map((r) => ({
        ...r,
        building_name: building,
        building_location: 'Lausanne',
      })),
    );
  });

  // ─── Locations ─────────────────────────────────────────────────────────────
  await context.route(/.*\/api\/v1\/locations\/search/, (route) => {
    const url = new URL(route.request().url());
    const q = (url.searchParams.get('query') ?? '').toLowerCase();
    return json(
      route,
      LOCATIONS.filter((l) => l.name.toLowerCase().includes(q)).map((l) => ({
        ...l,
        latitude: 0,
        longitude: 0,
      })),
    );
  });

  await context.route(/.*\/api\/v1\/locations\/calculate-distance/, (route) => {
    const url = new URL(route.request().url());
    const o = Number(url.searchParams.get('origin_location_id'));
    const d = Number(url.searchParams.get('destination_location_id'));
    const trips = Number(url.searchParams.get('number_of_trips') ?? 1);
    return json(route, { distance_km: distanceBetween(o, d) * trips });
  });

  // ─── Stats ─────────────────────────────────────────────────────────────────
  await context.route(
    /.*\/api\/v1\/modules-stats\/\d+\/report-stats/,
    (route) => json(route, REPORT_STATS),
  );

  // ─── Module endpoints (both report ids) ────────────────────────────────────
  const modulePath =
    /.*\/api\/v1\/carbon-reports\/(\d+)\/modules\/([^/?]+)(?:\/([^/?]+))?(?:\/(\d+))?(\?.*)?$/;

  await context.route(/.*\/api\/v1\/carbon-reports\/\d+\/modules\/$/, (route) =>
    json(route, []),
  );

  await context.route(modulePath, (route) => {
    const req = route.request();
    const m = req.url().match(modulePath)!;
    const reportId = Number(m[1]);
    const module = m[2];
    const sub = m[3];
    const itemId = m[4] ? Number(m[4]) : null;
    const method = req.method();

    // Module-level (?preview_limit=0) → counts
    if (!sub) {
      const totals: Record<number, number> = {};
      SUBMODULES.filter((s) => s.module === module).forEach((s) => {
        totals[s.enumId] = rowsOf(reportId, module, s.sub).length;
      });
      return json(route, buildModuleTotalsResponse(module, totals));
    }

    if (sub === 'members') {
      return json(route, [
        { institutional_id: 'sciper-1', name: 'Test Member' },
      ]);
    }
    if (sub === 'trips-map') return json(route, { trips: [] });
    if (sub === 'top-class-breakdown') return json(route, []);

    if (method === 'POST') {
      const row = insert(reportId, module, sub, parseJsonBody(req));
      return json(route, row, 201);
    }
    if (method === 'PATCH' && itemId != null) {
      const rows = rowsOf(reportId, module, sub);
      const row = rows.find((r) => r.id === itemId);
      if (!row) return route.fulfill({ status: 404, body: '' });
      Object.assign(row, parseJsonBody(req));
      if (sub !== 'planner_headcount') row.kg_co2eq = fakeKgCo2eq(sub, row);
      return json(route, row);
    }
    if (method === 'DELETE' && itemId != null) {
      const rows = rowsOf(reportId, module, sub);
      const idx = rows.findIndex((r) => r.id === itemId);
      if (idx >= 0) rows.splice(idx, 1);
      return route.fulfill({ status: 204, body: '' });
    }

    const items = rowsOf(reportId, module, sub);
    return json(route, {
      id: sub,
      name: sub,
      items,
      summary: {
        total_items: items.length,
        total_kg_co2eq: items.reduce((s, r) => s + num(r.kg_co2eq), 0),
      },
    });
  });

  // ─── CSV import pipeline ───────────────────────────────────────────────────
  await context.route('**/api/v1/files/temp-upload', (route) => {
    const body = route.request().postData() ?? '';
    pendingCsvRows = parseCsv(extractCsvFromMultipart(body));
    return json(route, [
      {
        name: 'data.csv',
        path: '/tmp/data.csv',
        size: body.length,
        mime_type: 'text/csv',
      },
    ]);
  });

  // Print/explore page's fetchAllData batches taxonomy fetches as one
  // .../data-entries call per module instead of one per submodule
  // (#2049 T6) — returns a map keyed by entry, not one TaxonomyNode.
  // Registered after the catch-all above so LIFO picks this more
  // specific route first for that path.
  await page.route('**/api/v1/taxonomies/module/*/data-entries*', (route) => {
    const entries = new URL(route.request().url()).searchParams.getAll(
      'entries',
    );
    const body = Object.fromEntries(
      entries.map((entry) => [entry, { name: entry, label: '', children: [] }]),
    );
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });

  // All other module preview_limit=0 calls (non-headcount modules).
  // Identity-addressed by the explore report id (99).
  await page.route(
    /.*\/api\/v1\/carbon-reports\/99\/modules\/[^/?]+\?.*preview_limit/,
    (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildModuleTotalsResponse('unknown', {})),
      });
    },
  );

  let nextJobId = 1;
  await context.route('**/api/v1/sync/dispatch', (route) => {
    const body = parseJsonBody(route.request()) as {
      config?: { data_entry_type_id?: number; module_type_id?: number };
    };
    const def = SUBMODULES.find(
      (s) => s.enumId === Number(body.config?.data_entry_type_id),
    );
    if (def) {
      pendingCsvRows.forEach((r) =>
        insert(EXPLORER_REPORT_ID, def.module, def.sub, r),
      );
    }
    pendingCsvRows = [];
    return json(route, { job_id: nextJobId++ });
  });

  // ─── Reports / workspace / session ─────────────────────────────────────────
  await context.route(
    /.*\/api\/v1\/carbon-reports\/simulator\/explore\/unit\/10\/reference-year\/2024\//,
    (route) => {
      if (route.request().method() === 'POST') {
        exploreReportCreated = true;
        return json(route, MOCK_SIMULATOR_REPORT);
      }
      if (!exploreReportCreated)
        return route.fulfill({ status: 404, body: '' });
      return json(route, MOCK_SIMULATOR_REPORT);
    },
  );

  await context.route(/.*\/api\/v1\/year-configuration\/$/, (route) =>
    json(route, [
      {
        year: YEAR,
        is_started: true,
        configuration_completed: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]),
  );
  await context.route(/.*\/api\/v1\/year-configuration\/\d+$/, (route) =>
    json(route, YEAR_CONFIG),
  );

  await context.route(
    /.*\/api\/v1\/carbon-reports\/unit\/10\/year\/2024\/$/,
    (route) => json(route, MOCK_CARBON_REPORT),
  );

  await context.route(/.*\/api\/v1\/users\/units$/, (route) =>
    json(route, [MOCK_UNIT]),
  );

  await context.route(/.*\/api\/v1\/workspace\/10\/2024\/home$/, (route) =>
    json(route, {
      carbon_report_id: MOCK_CARBON_REPORT.id,
      module_states: [],
      year_config: YEAR_CONFIG,
      stats: REPORT_STATS,
    }),
  );

  await context.route(/.*\/api\/v1\/session$/, (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    return json(route, {
      user: buildUser(role),
      units: [MOCK_UNIT],
      configured_years: [],
    });
  });

  return {
    requests,
    rows: (reportId, module, sub) => rowsOf(reportId, module, sub),
  };
}
