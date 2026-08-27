/**
 * HTTP-boundary mocks for the Research Facilities manual-input form (#2007).
 *
 * Deliberately does NOT set ``__LIGHTHOUSE_BYPASS__``: ``workspaceGuard``
 * returns early on that flag and never populates ``yearConfigStore.config``,
 * which is the very thing the ``inputs_deactivated`` scenario asserts on.
 * Same rationale as ``home-module-visibility-mocks.ts``.
 *
 * Since #2391 decision 1 the taxonomy endpoint is the select's only option
 * source. The shipped bug was exactly those two sources disagreeing — the
 * catalog carried the acronym while the taxonomy relabelled it with the unit
 * code — so there is now a single payload to get right.
 */
import type { Page } from '@playwright/test';

export const RF_URL = '/en/10/2024/research-facilities';

/** research_facilities / animal_facilities DataEntryTypeEnum values. */
export const COMMON_DET = 70;
export const ANIMAL_DET = 71;

const CARBON_REPORT_ID = 42;

const MOCK_USER = {
  id: 1,
  email: 'test@example.com',
  display_name: 'Test User',
  institutional_id: 'test-user',
  roles_raw: [],
  permissions: {
    'modules.research_facilities': ['view', 'edit'],
  },
};

const MOCK_UNIT = {
  id: 10,
  name: '10',
  institutional_id: 'unit-10',
  principal_user_id: 'user-1',
  principal_user_function: 'Test',
  principal_user_name: 'Test User',
  affiliations: [],
  current_user_role: 'principal',
};

/**
 * Real EPFL shapes: the id is an opaque unit code, the acronym users know the
 * platform by lives in `researchfacility_name`, and `use_unit` differs per
 * platform (a share, machine time, spend, animal housings).
 */
export const COMMON_FACTORS = [
  {
    factor_id: 1,
    researchfacility_id: '1902',
    researchfacility_name: 'SCITAS-GE',
    use_unit: 'CHF',
    total_use: 2195625.795,
  },
  {
    factor_id: 2,
    researchfacility_id: '0872',
    researchfacility_name: 'CAM-GE',
    use_unit: '%',
    total_use: 100,
  },
  {
    factor_id: 3,
    researchfacility_id: '0619',
    researchfacility_name: 'ISIC-NMRP',
    use_unit: 'hours',
    total_use: 56378.9439,
  },
];

export const ANIMAL_FACTORS = [
  {
    factor_id: 4,
    researchfacility_id: '1321',
    researchfacility_name: 'CPG',
    researchfacility_type: 'rodent',
    use_unit: 'housings',
    total_use: 3917,
  },
  {
    factor_id: 5,
    researchfacility_id: '1321',
    researchfacility_name: 'CPG',
    researchfacility_type: 'fish',
    use_unit: 'housings',
    total_use: 602,
  },
];

/**
 * What the backend builds from `kind_label_field` (the acronym label) and
 * `taxonomy_meta_fields` (the metric unit, #2391).
 */
function taxonomyFor(det: number) {
  if (det === ANIMAL_DET) {
    return {
      name: 'animal_facilities',
      label: 'Animal facilities',
      children: [
        {
          name: '1321',
          label: 'CPG',
          translation_key: '1321',
          meta: { use_unit: 'housings' },
          children: ANIMAL_FACTORS.map((f) => ({
            name: f.researchfacility_type,
            label: f.researchfacility_type,
            translation_key: f.researchfacility_type,
            meta: { use_unit: f.use_unit },
          })),
        },
      ],
    };
  }
  return {
    name: 'research_facilities',
    label: 'Research facilities',
    children: COMMON_FACTORS.map((f) => ({
      name: f.researchfacility_id,
      label: f.researchfacility_name,
      translation_key: f.researchfacility_id,
      meta: { use_unit: f.use_unit },
    })),
  };
}

function emptySubmodule(id: string) {
  return {
    id,
    name: id,
    count: 0,
    items: [],
    has_more: false,
    summary: {
      total_items: 0,
      annual_consumption_kwh: 0,
      total_kg_co2eq: 0,
    },
    // #951 — a manual row is the user's own: addable, deletable, editable.
    data_entry_policies: {
      user: {
        create: true,
        delete: true,
        editable_fields: [
          'researchfacility_id',
          'researchfacility_name',
          'use',
          'use_unit',
          'note',
        ],
      },
      imported: { create: false, delete: false, editable_fields: ['note'] },
    },
  };
}

function yearConfig(options: { inputsDeactivated: boolean }) {
  const submodule = {
    enabled: true,
    threshold: null,
    inputs_deactivated: options.inputsDeactivated,
    csv_deactivated: options.inputsDeactivated,
    incomplete: false,
    incomplete_reasons: [],
  };
  return {
    year: 2024,
    is_started: true,
    configuration_completed: '2024-01-01T00:00:00Z',
    config: {
      modules: {
        '6': {
          enabled: true,
          uncertainty_tag: 'medium',
          incomplete: false,
          submodules: {
            [String(COMMON_DET)]: submodule,
            [String(ANIMAL_DET)]: submodule,
          },
        },
      },
      reduction_objectives: {
        files: {
          institutional_footprint: null,
          population_projections: null,
          unit_scenarios: null,
        },
        goals: [],
        institutional_footprint: [],
        population_projections: [],
        unit_scenarios: [],
      },
    },
    recalculation_status: [],
    updated_at: '2024-01-01T00:00:00Z',
  };
}

export interface RfMockOptions {
  /** Backoffice switch: hides the form, shows the deactivated notice. */
  inputsDeactivated?: boolean;
  /** Drop the taxonomy, to prove the select's labels don't depend on it. */
  taxonomyUnavailable?: boolean;
  /** Collects create payloads so a test can assert what was submitted. */
  created?: Record<string, unknown>[];
}

export async function mockResearchFacilitiesBackend(
  page: Page,
  options: RfMockOptions = {},
): Promise<void> {
  const {
    inputsDeactivated = false,
    taxonomyUnavailable = false,
    created,
  } = options;

  // Registered FIRST = lowest priority under Playwright's LIFO route
  // evaluation, so it only absorbs what the specific routes below don't.
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, body: '' }),
  );

  const json = (body: unknown) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

  await page.route(/.*\/api\/v1\/session$/, (route) =>
    route.fulfill(
      json({
        user: MOCK_USER,
        units: [MOCK_UNIT],
        configured_years: [2024],
      }),
    ),
  );

  await page.route(/.*\/api\/v1\/workspace\/10\/2024\/home$/, (route) =>
    route.fulfill(
      json({
        carbon_report_id: CARBON_REPORT_ID,
        year_config: yearConfig({ inputsDeactivated }),
        stats: {
          buckets: {},
          per_fte: {},
          validated_buckets: [],
          total_fte: 0,
          total_tonnes_validated_co2eq: 0,
        },
      }),
    ),
  );

  await page.route(
    /.*\/api\/v1\/carbon-reports\/unit\/10\/year\/2024\/?$/,
    (route) => route.fulfill(json({ id: CARBON_REPORT_ID })),
  );

  await page.route(
    /.*\/api\/v1\/carbon-reports\/42\/modules\/?(\?.*)?$/,
    (route) => route.fulfill(json([])),
  );

  // Submodule rows — POST is the create under test, GET returns the table.
  await page.route(
    /.*\/api\/v1\/carbon-reports\/42\/modules\/research-facilities\/(research-facilities|animal_facilities)(\?.*)?$/,
    async (route) => {
      const url = route.request().url();
      const submoduleId = url.includes('animal_facilities')
        ? 'animal_facilities'
        : 'research-facilities';
      if (route.request().method() === 'POST') {
        created?.push(route.request().postDataJSON());
        return route.fulfill({ ...json({ id: 1 }), status: 201 });
      }
      return route.fulfill(json(emptySubmodule(submoduleId)));
    },
  );

  await page.route(
    /.*\/api\/v1\/carbon-reports\/42\/modules\/research-facilities(\?.*)?$/,
    (route) =>
      route.fulfill(
        json({
          module_type: 'research-facilities',
          unit: 10,
          year: '2024',
          data_entry_types_total_items: { [COMMON_DET]: 0, [ANIMAL_DET]: 0 },
          carbon_report_module_id: 7,
          retrieved_at: '2024-01-01T00:00:00Z',
          submodules: {
            'research-facilities': emptySubmodule('research-facilities'),
            animal_facilities: emptySubmodule('animal_facilities'),
          },
          totals: { total_submodules: 2, total_items: 0, total_kg_co2eq: 0 },
        }),
      ),
  );

  await page.route(
    /.*\/api\/v1\/taxonomies\/module\/research-facilities\/(\S+?)(\?.*)?$/,
    (route) => {
      if (taxonomyUnavailable) return route.fulfill({ status: 404, body: '' });
      const det = route.request().url().includes('animal_facilities')
        ? ANIMAL_DET
        : COMMON_DET;
      return route.fulfill(json(taxonomyFor(det)));
    },
  );

  // Factor values mirrored into the form on selection (name + use_unit).
  await page.route(
    /.*\/api\/v1\/factors\/(70|71)\/classes\/([^/]+)\/values(\?.*)?$/,
    (route) => {
      const url = new URL(route.request().url());
      const facilityId = decodeURIComponent(
        url.pathname.split('/classes/')[1].split('/values')[0],
      );
      const subClass = url.searchParams.get('sub_class');
      const pool = url.pathname.includes('/71/')
        ? ANIMAL_FACTORS
        : COMMON_FACTORS;
      const factor = pool.find(
        (f) =>
          f.researchfacility_id === facilityId &&
          (!subClass ||
            (f as { researchfacility_type?: string }).researchfacility_type ===
              subClass),
      );
      return route.fulfill(json(factor ?? null));
    },
  );
}
