/**
 * Integration tests for the CO₂ Simulator Explorer (issue #1793).
 *
 * The HTTP boundary is a stateful fake backend (``setup/simulator-mocks.ts``):
 * rows POSTed from the forms or imported through the CSV dialog are stored in
 * memory and served back by the list endpoints, so every "data displayed in
 * table" assertion goes through the real page → store → API → table path.
 *
 * "Matches calculator" checks render the calculator module page under the
 * same mocks and compare the dropdown options / form labels with the
 * explorer's.
 */
import { test, expect, type Locator, type Page } from '@playwright/test';
import {
  calculatorModuleUrl,
  EXPLORER_REPORT_ID,
  installExplorerInitScripts,
  MAIN_TOTAL_TONNES,
  mockExplorerBackend,
  SIMULATOR_URL,
  type FakeBackend,
  type MockRole,
} from './setup/simulator-mocks';

const ISSUE_MODULE_ORDER = [
  'Headcount',
  'Process emissions',
  'Buildings',
  'Equipment',
  'External clouds & AI',
  'Professional travel',
  'Purchases',
];

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const exact = (s: string) => new RegExp(`^${escapeRe(s)}$`);
/** Submodule titles switch between singular and plural with the count. */
const titleRe = (title: string) =>
  new RegExp(
    `^${title
      .split(' ')
      .map((w) => escapeRe(w).replace(/s$/, 's?'))
      .join(' ')} \\(`,
  );

// ─── Page helpers ────────────────────────────────────────────────────────────

async function openExplorer(
  page: Page,
  context: Parameters<typeof installExplorerInitScripts>[0],
  role: MockRole = 'principal',
): Promise<FakeBackend> {
  await installExplorerInitScripts(context);
  const backend = await mockExplorerBackend(page, { role });
  await page.goto(SIMULATOR_URL);
  await expect(page.locator('.q-expansion-item').first()).toBeVisible({
    timeout: 15000,
  });
  return backend;
}

/** Top-level module headers (the explorer's own `div.text-h5` inside the flex header). */
function moduleHeaders(page: Page): Locator {
  return page.locator('.q-item .flex.items-center > div.text-h5');
}

/** The expansion item of a top-level module, expanded. */
async function openModule(page: Page, label: string): Promise<Locator> {
  const header = moduleHeaders(page).filter({ hasText: exact(label) });
  const section = page
    .locator('.q-expansion-item')
    .filter({ has: header })
    .first();
  const headerItem = section.locator('.q-item').first();
  if ((await headerItem.getAttribute('aria-expanded')) !== 'true') {
    await headerItem.click();
  }
  return section;
}

/** A submodule section inside a module section, expanded. */
async function openSubmodule(
  moduleSection: Locator,
  titlePrefix: string,
): Promise<Locator> {
  const sub = moduleSection
    .locator('.module-submodule-section')
    .filter({
      has: moduleSection
        .page()
        .locator('.q-item span', { hasText: titleRe(titlePrefix) }),
    })
    .first();
  await expect(sub).toBeVisible();
  const headerItem = sub.locator('.q-item').first();
  if ((await headerItem.getAttribute('aria-expanded')) !== 'true') {
    await headerItem.click();
  }
  await expect(sub.locator('.co2-table')).toBeVisible();
  return sub;
}

function subTitle(sub: Locator): Locator {
  return sub.locator('.q-item span').first();
}

function field(scope: Locator, label: string): Locator {
  return scope
    .locator('.q-field')
    .filter({
      has: scope.page().locator('.q-field__label', {
        hasText: new RegExp(`^${escapeRe(label)}(\\s*\\(.*\\))?$`),
      }),
    })
    .first();
}

async function fillField(scope: Locator, label: string, value: string) {
  const input = field(scope, label).locator('input');
  await input.fill(value);
}

async function menuOptions(page: Page): Promise<string[]> {
  const menu = page.locator('.q-menu:visible').last();
  await expect(menu).toBeVisible();
  const texts = await menu.locator('.q-item').allInnerTexts();
  return texts.map((t) => t.trim());
}

async function selectOptions(scope: Locator, label: string): Promise<string[]> {
  const page = scope.page();
  await field(scope, label).click();
  const options = await menuOptions(page);
  await page.keyboard.press('Escape');
  await expect(page.locator('.q-menu:visible')).toHaveCount(0);
  return options;
}

async function pick(scope: Locator, label: string, option: string) {
  const page = scope.page();
  await field(scope, label).click();
  const menu = page.locator('.q-menu:visible').last();
  const items = menu.locator('.q-item');
  const exactMatch = items.filter({
    hasText: new RegExp(`^${escapeRe(option)}$`, 'i'),
  });
  if (await exactMatch.count()) await exactMatch.first().click();
  else await items.filter({ hasText: option }).first().click();
  await expect(page.locator('.q-menu:visible')).toHaveCount(0);
}

async function clickAdd(sub: Locator) {
  await sub.getByRole('button', { name: /^Add/ }).first().click();
}

function tableRows(sub: Locator): Locator {
  return sub
    .locator('.co2-table tbody tr')
    .filter({ hasNot: sub.page().locator('.q-table__bottom') });
}

/**
 * Value of a row cell by column header.  Explorer rows are editable inline,
 * so a cell's value may live in an input rather than in its text.
 */
async function cell(
  sub: Locator,
  row: Locator,
  header: string,
): Promise<string> {
  const headers = await sub.locator('.co2-table thead th').allInnerTexts();
  const idx = headers.findIndex(
    (h) => h.replace(/arrow_upward|info/g, '').trim() === header,
  );
  expect(
    idx,
    `column "${header}" in ${JSON.stringify(headers)}`,
  ).toBeGreaterThanOrEqual(0);
  const td = row.locator('td').nth(idx);
  const input = td.locator('input');
  if (await input.count()) return (await input.first().inputValue()).trim();
  return (await td.innerText()).replace(/expand_more|edit/g, '').trim();
}

async function importCsv(sub: Locator, csv: string) {
  const page = sub.page();
  await sub.getByRole('button', { name: 'Upload CSV' }).click();
  const dialog = page.locator('.q-dialog:visible');
  await expect(dialog.getByText('Upload CSV Files')).toBeVisible();
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'data.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(csv),
  });
  await dialog.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByText('CSV sync completed.')).toBeVisible();
}

async function openCalculatorModule(
  page: Page,
  module: string,
): Promise<Locator> {
  await page.goto(calculatorModuleUrl(module));
  const main = page.locator('main').last();
  await expect(main.locator('.module-submodule-section').first()).toBeVisible({
    timeout: 15000,
  });
  return main;
}

async function travelCity(
  form: Locator,
  which: 'From' | 'To',
  typed: string,
  city: string,
) {
  const page = form.page();
  const f = field(form, which);
  await f.locator('input').fill(typed);
  const menu = page.locator('.q-menu:visible').last();
  await menu.locator('.q-item').filter({ hasText: city }).first().click();
  await expect(page.locator('.q-menu:visible')).toHaveCount(0);
}

const plainNumber = (s: string) => Number(s.replace(/[^\d.-]/g, ''));

function fteInput(section: Locator, label: string): Locator {
  return section
    .locator('.headcount-table__row')
    .filter({ has: section.page().locator('label', { hasText: exact(label) }) })
    .locator('input');
}

// ─── Suite ───────────────────────────────────────────────────────────────────

test.describe('Explorer — general access', () => {
  test('modules are present and in the expected order', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const headers = (await moduleHeaders(page).allInnerTexts()).map((h) =>
      h.trim(),
    );
    const listed = headers.filter((h) => ISSUE_MODULE_ORDER.includes(h));
    expect(listed).toEqual(ISSUE_MODULE_ORDER);
  });

  for (const role of ['principal', 'std'] as MockRole[]) {
    test(`calco2.user.${role} can access every module`, async ({
      page,
      context,
    }) => {
      await openExplorer(page, context, role);
      expect(page.url()).toContain('/simulation/explore/');
      for (const label of ISSUE_MODULE_ORDER) {
        const section = await openModule(page, label);
        await expect(
          section.locator('.q-expansion-item__content').first(),
        ).toBeVisible();
        if (label === 'Headcount') {
          await expect(fteInput(section, 'Professors')).toBeVisible();
        } else {
          const firstSub = section.locator('.module-submodule-section').first();
          await expect(firstSub).toBeVisible();
          const title = (
            await firstSub.locator('.q-item span').first().innerText()
          ).replace(/\s*\(\d+\)\s*$/, '');
          const sub = await openSubmodule(section, title);
          await expect(
            sub.getByRole('button', { name: /^Add/ }).first(),
          ).toBeVisible();
        }
      }
    });
  }
});

test.describe('Explorer — Headcount (Personnel)', () => {
  test('job function list matches the calculator member form', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Headcount');
    const explorerLabels = (
      await section
        .locator('.headcount-table__row > label:not(.q-field)')
        .allInnerTexts()
    ).map((l) => l.trim());
    expect(explorerLabels).toHaveLength(9);

    const calc = await openCalculatorModule(page, 'headcount');
    const members = await openSubmodule(calc, 'Members');
    const calculatorFunctions = await selectOptions(members, 'Function');
    expect(calculatorFunctions).toEqual(explorerLabels.slice(0, 8));
  });

  test('adds several FTEs (0.4, 0.8, 1) and lists them', async ({
    page,
    context,
  }) => {
    const backend = await openExplorer(page, context);
    const section = await openModule(page, 'Headcount');

    const entries: [string, string][] = [
      ['Scientific collaborators', '0.4'],
      ['Professors', '0.8'],
      ['Students', '1'],
    ];
    for (const [label, value] of entries) {
      await fteInput(section, label).click();
      await fteInput(section, label).pressSequentially(value);
      await fteInput(section, label).press('Tab');
      await expect
        .poll(() =>
          backend.requests.some(
            (r) =>
              r.method === 'POST' &&
              r.url.includes(
                `/carbon-reports/${EXPLORER_REPORT_ID}/modules/headcount/planner_headcount`,
              ) &&
              r.body?.includes(`"fte":${value}`),
          ),
        )
        .toBe(true);
    }
    const stored = backend.rows(
      EXPLORER_REPORT_ID,
      'headcount',
      'planner_headcount',
    );
    expect(stored.map((r) => [r.sius_code, r.fte])).toEqual([
      ['53', 0.4],
      ['51', 0.8],
      ['student', 1],
    ]);

    await page.reload();
    await expect(page.locator('.q-expansion-item').first()).toBeVisible();
    const again = await openModule(page, 'Headcount');
    await expect(fteInput(again, 'Scientific collaborators')).toHaveValue(
      '0.4',
    );
    await expect(fteInput(again, 'Professors')).toHaveValue('0.8');
    await expect(fteInput(again, 'Students')).toHaveValue('1');
  });
});

test.describe('Explorer — Process emissions', () => {
  test('gas dropdown matches the calculator', async ({ page, context }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Process emissions');
    const sub = await openSubmodule(section, 'Process emissions');
    const explorerGases = await selectOptions(sub, 'Emitted gas');
    expect(explorerGases).toEqual(['CO₂', 'CH₄', 'SF₆']);
    const explorerLabels = await sub.locator('.q-field__label').allInnerTexts();

    const calc = await openCalculatorModule(page, 'process-emissions');
    const calcSub = await openSubmodule(calc, 'Process emissions');
    expect(await selectOptions(calcSub, 'Emitted gas')).toEqual(explorerGases);
    expect(await calcSub.locator('.q-field__label').allInnerTexts()).toEqual(
      explorerLabels,
    );
  });

  test('adds gases with different quantities, each with its own kg CO₂-eq', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Process emissions');
    const sub = await openSubmodule(section, 'Process emissions');

    await clickAdd(sub);
    await expect(sub.getByText('Required').first()).toBeVisible();

    await pick(sub, 'Emitted gas', 'CO₂');
    await pick(sub, 'Sub-category', 'fossil');
    await fillField(sub, 'Quantity (kg)', '10');
    await clickAdd(sub);
    await expect(subTitle(sub)).toHaveText(/Process emission \(1\)/);

    await pick(sub, 'Emitted gas', 'CH₄');
    await pick(sub, 'Sub-category', 'biogenic');
    await fillField(sub, 'Quantity (kg)', '2');
    await clickAdd(sub);
    await expect(subTitle(sub)).toHaveText(/Process emissions \(2\)/);

    const rows = tableRows(sub);
    await expect(rows).toHaveCount(2);
    const seen = [];
    for (let i = 0; i < 2; i++) {
      const row = rows.nth(i);
      seen.push([
        await cell(sub, row, 'Emitted gas'),
        plainNumber(await cell(sub, row, 'Quantity (kg)')),
        plainNumber(await cell(sub, row, 'kg CO₂-eq')),
      ]);
    }
    expect(seen).toEqual(
      expect.arrayContaining([
        ['CO₂', 10, 10],
        ['CH₄', 2, 56],
      ]),
    );
  });

  test('imports gases from CSV', async ({ page, context }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Process emissions');
    const sub = await openSubmodule(section, 'Process emissions');
    await importCsv(
      sub,
      'category,subcategory,quantity_kg\nco2,fossil,5\nsf6,electrical,0.5\n',
    );
    await expect(tableRows(sub)).toHaveCount(2);
    const kgs = [];
    for (let i = 0; i < 2; i++)
      kgs.push(
        plainNumber(await cell(sub, tableRows(sub).nth(i), 'kg CO₂-eq')),
      );
    expect(kgs.sort((a, b) => a - b)).toEqual([5, 11750]);
  });
});

test.describe('Explorer — Buildings', () => {
  test('heating type and building dropdowns match the calculator', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Buildings');
    const combustion = await openSubmodule(
      section,
      'Energy Combustions Emissions',
    );
    const rooms = await openSubmodule(section, 'Rooms');
    const heating = await selectOptions(combustion, 'Heating type');
    const buildings = await selectOptions(rooms, 'Building');
    expect(heating).toEqual(['Natural gas', 'Heating oil', 'Pellets']);
    expect(buildings).toEqual(['BC', 'GC']);

    const calc = await openCalculatorModule(page, 'buildings');
    const calcCombustion = await openSubmodule(
      calc,
      'Energy Combustions Emissions',
    );
    const calcRooms = await openSubmodule(calc, 'Rooms');
    expect(await selectOptions(calcCombustion, 'Heating type')).toEqual(
      heating,
    );
    expect(await selectOptions(calcRooms, 'Building')).toEqual(buildings);
  });

  test('adds heating types with different quantities and a room', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Buildings');
    const combustion = await openSubmodule(
      section,
      'Energy Combustions Emissions',
    );

    await pick(combustion, 'Heating type', 'Natural gas');
    await expect(field(combustion, 'Unit').locator('input')).toHaveValue('kWh');
    await fillField(combustion, 'Quantity', '100');
    await clickAdd(combustion);
    await expect(subTitle(combustion)).toHaveText(
      /Energy Combustion Emissions \(1\)/,
    );

    await pick(combustion, 'Heating type', 'Heating oil');
    await fillField(combustion, 'Quantity', '50');
    await clickAdd(combustion);
    await expect(subTitle(combustion)).toHaveText(
      /Energy Combustions Emissions \(2\)/,
    );

    const rows = tableRows(combustion);
    const seen = [];
    for (let i = 0; i < 2; i++) {
      seen.push([
        await cell(combustion, rows.nth(i), 'Heating type'),
        plainNumber(await cell(combustion, rows.nth(i), 'kg CO₂-eq')),
      ]);
    }
    expect(seen).toEqual(
      expect.arrayContaining([
        ['Natural gas', 20],
        ['Heating oil', 15],
      ]),
    );

    const rooms = await openSubmodule(section, 'Rooms');
    await pick(rooms, 'Building', 'BC');
    await pick(rooms, 'Room', 'BC 101');
    await expect(field(rooms, 'Surface (m²)').locator('input')).toHaveValue(
      '20',
    );
    await expect(field(rooms, 'Heating (kWh/m²)').locator('input')).toHaveValue(
      '50',
    );
    await clickAdd(rooms);
    await expect(subTitle(rooms)).toHaveText(/Room \(1\)/);
    const roomRow = tableRows(rooms).first();
    expect(await cell(rooms, roomRow, 'Room')).toBe('BC 101');
    expect(plainNumber(await cell(rooms, roomRow, 'kg CO₂-eq'))).toBe(190);
  });

  test('imports combustion and room CSVs', async ({ page, context }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Buildings');
    const combustion = await openSubmodule(
      section,
      'Energy Combustions Emissions',
    );
    await importCsv(combustion, 'name,unit,quantity\npellets,kWh,200\n');
    await expect(tableRows(combustion)).toHaveCount(1);
    expect(
      plainNumber(
        await cell(combustion, tableRows(combustion).first(), 'kg CO₂-eq'),
      ),
    ).toBe(10);

    const rooms = await openSubmodule(section, 'Rooms');
    await importCsv(
      rooms,
      'building_name,room_name,room_type,room_surface_square_meter,room_allocation_ratio,heating_kwh_per_square_meter\nGC,GC A1,office,30,1,10\n',
    );
    await expect(tableRows(rooms)).toHaveCount(1);
    expect(await cell(rooms, tableRows(rooms).first(), 'Room')).toBe('GC A1');
  });
});

test.describe('Explorer — Equipment', () => {
  const SUBS = ['Scientific equipment', 'IT equipments', 'Other equipments'];

  test('equipment class dropdown matches the calculator', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Equipment');
    const explorerClasses: Record<string, string[]> = {};
    for (const title of SUBS) {
      const sub = await openSubmodule(section, title);
      explorerClasses[title] = await selectOptions(sub, 'Class');
    }
    expect(explorerClasses['Scientific equipment']).toEqual([
      'Centrifuge',
      'Microscope',
    ]);

    const calc = await openCalculatorModule(page, 'equipment');
    for (const title of SUBS) {
      const sub = await openSubmodule(calc, title);
      expect(await selectOptions(sub, 'Class')).toEqual(explorerClasses[title]);
    }
  });

  test('caps active + standby usage at 168 h/week and computes kg CO₂-eq', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Equipment');
    const sub = await openSubmodule(section, 'Scientific equipment');

    await fillField(sub, 'Name', 'Centrifuge A');
    await fillField(sub, 'Equipment ID', 'EQ-1');
    await pick(sub, 'Class', 'Centrifuge');
    await pick(sub, 'Sub-class', 'Benchtop');
    await expect(field(sub, 'Active power (W)').locator('input')).toHaveValue(
      '500',
    );
    await fillField(sub, 'Active usage (h/week)', '100');
    await fillField(sub, 'Standby usage (h/week)', '100');
    await clickAdd(sub);
    await expect(sub.getByText('Max usages 168 hrs/wk').first()).toBeVisible();
    await expect(subTitle(sub)).toHaveText(/\(0\)/);

    await fillField(sub, 'Standby usage (h/week)', '60');
    await clickAdd(sub);
    await expect(subTitle(sub)).toHaveText(/Scientific equipment \(1\)/);
    const row = tableRows(sub).first();
    expect(await cell(sub, row, 'Name')).toBe('Centrifuge A');
    expect(plainNumber(await cell(sub, row, 'kg CO₂-eq'))).toBe(2756);
  });

  test('imports a CSV into each equipment sub-section', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Equipment');
    const csvs: Record<string, string> = {
      'Scientific equipment':
        'name,equipment_id,equipment_class,sub_class,active_usage_hours_per_week,standby_usage_hours_per_week,active_power_w,standby_power_w\nSpectro,EQ-9,Microscope,Optical,10,10,500,50\n',
      'IT equipments':
        'name,equipment_id,equipment_class,active_usage_hours_per_week,standby_usage_hours_per_week,active_power_w,standby_power_w\nDell,IT-1,Laptop,40,0,100,10\n',
      'Other equipments':
        'name,equipment_id,equipment_class,sub_class,active_usage_hours_per_week,standby_usage_hours_per_week,active_power_w,standby_power_w\nULT,OT-1,Freezer,-80 °C,168,0,300,30\n',
    };
    const expectedKg: Record<string, number> = {
      'Scientific equipment': 286,
      'IT equipments': 208,
      'Other equipments': 2621,
    };
    for (const title of SUBS) {
      const sub = await openSubmodule(section, title);
      await importCsv(sub, csvs[title]);
      await expect(tableRows(sub)).toHaveCount(1);
      expect(
        plainNumber(await cell(sub, tableRows(sub).first(), 'kg CO₂-eq')),
      ).toBe(expectedKg[title]);
    }
  });
});

test.describe('Explorer — External clouds & AI', () => {
  test('provider dropdowns match the calculator', async ({ page, context }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'External clouds & AI');
    const clouds = await openSubmodule(section, 'External cloud services');
    const ai = await openSubmodule(section, 'External AI services');
    const cloudProviders = await selectOptions(clouds, 'Provider');
    const aiProviders = await selectOptions(ai, 'Provider');
    expect(cloudProviders).toEqual(['AWS', 'Azure']);
    expect(aiProviders).toEqual(['OpenAI', 'Anthropic']);

    const calc = await openCalculatorModule(page, 'external-cloud-and-ai');
    expect(
      await selectOptions(
        await openSubmodule(calc, 'External cloud services'),
        'Provider',
      ),
    ).toEqual(cloudProviders);
    expect(
      await selectOptions(
        await openSubmodule(calc, 'External AI services'),
        'Provider',
      ),
    ).toEqual(aiProviders);
  });

  test('lists clouds and AIs in their own tables with kg CO₂-eq', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'External clouds & AI');
    const clouds = await openSubmodule(section, 'External cloud services');
    const ai = await openSubmodule(section, 'External AI services');

    await pick(clouds, 'Provider', 'AWS');
    await pick(clouds, 'Service Type', 'virtualisation');
    await fillField(clouds, 'Spending', '100');
    await clickAdd(clouds);
    await expect(subTitle(clouds)).toHaveText(/External cloud service \(1\)/);

    await pick(ai, 'Provider', 'OpenAI');
    await pick(ai, 'Use', 'chat');
    await fillField(ai, 'Number of users (FTE)', '2');
    await pick(ai, 'Frequency (number of times per day)', '5–20 times/day');
    await clickAdd(ai);
    await expect(subTitle(ai)).toHaveText(/External AI service \(1\)/);

    await expect(tableRows(clouds)).toHaveCount(1);
    await expect(tableRows(ai)).toHaveCount(1);
    expect(await cell(clouds, tableRows(clouds).first(), 'Provider')).toBe(
      'AWS',
    );
    expect(
      plainNumber(await cell(clouds, tableRows(clouds).first(), 'kg CO₂-eq')),
    ).toBe(50);
    expect(await cell(ai, tableRows(ai).first(), 'Provider')).toBe('OpenAI');
    expect(
      plainNumber(await cell(ai, tableRows(ai).first(), 'kg CO₂-eq')),
    ).toBe(80);
  });

  test('imports cloud and AI CSVs', async ({ page, context }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'External clouds & AI');
    const clouds = await openSubmodule(section, 'External cloud services');
    await importCsv(
      clouds,
      'provider,service_type,spent_amount,currency\nAzure,calcul,20,eur\n',
    );
    await expect(tableRows(clouds)).toHaveCount(1);
    expect(
      plainNumber(await cell(clouds, tableRows(clouds).first(), 'kg CO₂-eq')),
    ).toBe(10);

    const ai = await openSubmodule(section, 'External AI services');
    await importCsv(
      ai,
      'provider,usage_type,fte_count,requests_per_user_per_day\nAnthropic,chat,1,gt_100\n',
    );
    await expect(tableRows(ai)).toHaveCount(1);
    expect(
      plainNumber(await cell(ai, tableRows(ai).first(), 'kg CO₂-eq')),
    ).toBe(500);
  });
});

test.describe('Explorer — Professional travel', () => {
  test('city selection works like the calculator for planes and trains', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Professional travel');
    const explorerDistances: Record<string, string> = {};
    const calcDistances: Record<string, string> = {};

    for (const scope of ['explorer', 'calculator'] as const) {
      const root =
        scope === 'explorer'
          ? section
          : await openCalculatorModule(page, 'professional-travel');
      const plane = await openSubmodule(root, 'Plane trips');
      await travelCity(plane, 'From', 'Gen', 'Geneva');
      await travelCity(plane, 'To', 'Par', 'Paris');
      await expect(
        field(plane, 'Distance (km)').locator('input'),
      ).not.toHaveValue('');
      const train = await openSubmodule(root, 'Train trips');
      await travelCity(train, 'From', 'Laus', 'Lausanne');
      await travelCity(train, 'To', 'Zur', 'Zurich');
      await expect(
        field(train, 'Distance (km)').locator('input'),
      ).not.toHaveValue('');
      const target = scope === 'explorer' ? explorerDistances : calcDistances;
      target.plane = await field(plane, 'Distance (km)')
        .locator('input')
        .inputValue();
      target.train = await field(train, 'Distance (km)')
        .locator('input')
        .inputValue();
      expect(await selectOptions(plane, 'Class')).toEqual([
        'Business',
        'Economy',
      ]);
      expect(await selectOptions(train, 'Class')).toEqual([
        '1st class',
        '2nd class',
      ]);
    }
    expect(explorerDistances).toEqual(calcDistances);
    expect(plainNumber(explorerDistances.plane)).toBe(400);
  });

  test('lists train and plane trips in their tables with distance/class-dependent kg CO₂-eq', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Professional travel');
    const plane = await openSubmodule(section, 'Plane trips');
    const train = await openSubmodule(section, 'Train trips');

    await travelCity(plane, 'From', 'Gen', 'Geneva');
    await travelCity(plane, 'To', 'Lon', 'London');
    await pick(plane, 'Class', 'Economy');
    await clickAdd(plane);
    await expect(subTitle(plane)).toHaveText(/Plane trip \(1\)/);

    await travelCity(plane, 'From', 'Gen', 'Geneva');
    await travelCity(plane, 'To', 'Par', 'Paris');
    await pick(plane, 'Class', 'Business');
    await clickAdd(plane);
    await expect(subTitle(plane)).toHaveText(/Plane trips \(2\)/);

    await travelCity(train, 'From', 'Laus', 'Lausanne');
    await travelCity(train, 'To', 'Zur', 'Zurich');
    await fillField(train, 'Number of trips', '3');
    await pick(train, 'Class', '2nd class');
    await clickAdd(train);
    await expect(subTitle(train)).toHaveText(/Train trip \(1\)/);

    const planeRows = tableRows(plane);
    await expect(planeRows).toHaveCount(2);
    const planes = [];
    for (let i = 0; i < 2; i++) {
      planes.push([
        await cell(plane, planeRows.nth(i), 'From'),
        plainNumber(await cell(plane, planeRows.nth(i), 'Distance (km)')),
        plainNumber(await cell(plane, planeRows.nth(i), 'kg CO₂-eq')),
      ]);
    }
    expect(planes).toEqual(
      expect.arrayContaining([
        ['Geneva (GVA)', 800, 160],
        ['Geneva (GVA)', 400, 200],
      ]),
    );
    await expect(tableRows(train)).toHaveCount(1);
    expect(
      plainNumber(await cell(train, tableRows(train).first(), 'kg CO₂-eq')),
    ).toBe(12);
  });

  test('imports plane and train CSVs', async ({ page, context }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Professional travel');
    const plane = await openSubmodule(section, 'Plane trips');
    await importCsv(
      plane,
      'origin_name,destination_name,number_of_trips,cabin_class\nGeneva,London,1,economy\n',
    );
    await expect(tableRows(plane)).toHaveCount(1);
    expect(await cell(plane, tableRows(plane).first(), 'To')).toBe(
      'London (LHR)',
    );

    const train = await openSubmodule(section, 'Train trips');
    await importCsv(
      train,
      'origin_name,destination_name,number_of_trips,cabin_class\nLausanne,Zurich,2,first\n',
    );
    await expect(tableRows(train)).toHaveCount(1);
    expect(
      plainNumber(await cell(train, tableRows(train).first(), 'kg CO₂-eq')),
    ).toBe(16);
  });
});

test.describe('Explorer — Purchases', () => {
  const CSV_SUBS = [
    'Scientific equipment',
    'IT equipment',
    'Consumables & accessories',
    'Biological, chemical & gaseous products',
    'Services',
    'Vehicles',
    'Other purchases',
  ];

  test('CSV import is offered for every sub-section except Centralized purchases', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Purchases');
    for (const title of CSV_SUBS) {
      const sub = await openSubmodule(section, title);
      await expect(
        sub.getByRole('button', { name: 'Upload CSV' }),
      ).toBeVisible();
      await expect(
        sub.getByRole('button', { name: /^Add/ }).first(),
      ).toBeVisible();
    }
    const centralized = await openSubmodule(section, 'Centralized purchases');
    await expect(
      centralized.getByRole('button', { name: 'Upload CSV' }),
    ).toHaveCount(0);
    await expect(
      centralized.getByRole('button', { name: /^Add/ }).first(),
    ).toBeVisible();

    const services = await openSubmodule(section, 'Services');
    await importCsv(
      services,
      'name,supplier,purchase_institutional_code,quantity,total_spent_amount,currency\nAudit,KPMG,Consulting,1,1000,chf\n',
    );
    await expect(tableRows(services)).toHaveCount(1);
    expect(
      plainNumber(
        await cell(services, tableRows(services).first(), 'kg CO₂-eq'),
      ),
    ).toBe(400);
  });

  test('adds items listed in their respective tables with kg CO₂-eq', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Purchases');

    const sci = await openSubmodule(section, 'Scientific equipment');
    await fillField(sci, 'Item description', 'Spectrometer');
    await pick(sci, 'UNSPSC description', 'Laboratory equipment');
    await fillField(sci, 'Total spent amount', '100');
    await clickAdd(sci);
    await expect(subTitle(sci)).toHaveText(/Scientific equipment \(1\)/);

    const centralized = await openSubmodule(section, 'Centralized purchases');
    await pick(centralized, 'Item description', 'LN2');
    await expect(field(centralized, 'Unit').locator('input')).toHaveValue('kg');
    await fillField(centralized, 'Annual consumption', '10');
    await clickAdd(centralized);
    await expect(subTitle(centralized)).toHaveText(
      /Centralized purchases \(1\)/,
    );

    await expect(tableRows(sci)).toHaveCount(1);
    expect(await cell(sci, tableRows(sci).first(), 'Item description')).toBe(
      'Spectrometer',
    );
    expect(
      plainNumber(await cell(sci, tableRows(sci).first(), 'kg CO₂-eq')),
    ).toBe(40);
    await expect(tableRows(centralized)).toHaveCount(1);
    expect(
      plainNumber(
        await cell(centralized, tableRows(centralized).first(), 'kg CO₂-eq'),
      ),
    ).toBe(20);

    const it = await openSubmodule(section, 'IT equipment');
    await expect(tableRows(it)).toHaveCount(0);
  });
});

test.describe('Explorer — Simulation results', () => {
  const MAIN_CATEGORIES: [string, number][] = [
    ['Process emissions', 1.2],
    ['Thermal energy emissions', 0.8],
    ['Buildings', 2.5],
    ['Equipment', 3],
    ['External clouds & AI', 0.4],
    ['Professional travel', 5],
    ['Purchases', 6],
    ['Research facilities', 0.9],
  ];

  async function exportCsv(page: Page): Promise<string[][]> {
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page
        .locator('.module-carbon-chart')
        .getByRole('button', { name: 'CSV' })
        .click(),
    ]);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    const text = Buffer.concat(chunks).toString('utf8').replace(/^﻿/, '');
    return text
      .trim()
      .split('\n')
      .map((line) => line.split(','));
  }

  test('total carbon footprint equals the sum of all category values', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    await expect(page.locator('.big-number__value')).toHaveText(
      new RegExp(`^${Math.round(MAIN_TOTAL_TONNES)}\\D`),
    );

    const rows = await exportCsv(page);
    const sum = rows.slice(1).reduce((s, r) => s + Number(r[3]), 0);
    expect(sum).toBeCloseTo(MAIN_TOTAL_TONNES, 6);
    expect(sum).toBeCloseTo(
      MAIN_CATEGORIES.reduce((s, [, v]) => s + v, 0),
      6,
    );
  });

  test('chart groups categories into scopes 1, 2 and 3', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const chart = page.locator('.module-carbon-chart');
    await expect(chart.locator('canvas').first()).toBeVisible();

    const rows = await exportCsv(page);
    const byCategory = new Map<string, number>();
    for (const [category, , , co2] of rows.slice(1)) {
      byCategory.set(category, (byCategory.get(category) ?? 0) + Number(co2));
    }
    const scope1 = ['Process emissions', 'Thermal energy emissions'];
    const scope2 = ['Buildings', 'Equipment'];
    const scope3 = [
      'External clouds & AI',
      'Professional travel',
      'Purchases',
      'Research facilities',
    ];
    for (const cat of [...scope1, ...scope2, ...scope3]) {
      expect(byCategory.get(cat), cat).toBeGreaterThan(0);
    }
    expect([...byCategory.keys()]).toEqual([...scope1, ...scope2, ...scope3]);
    expect(rows[0]).toEqual([
      'category',
      'subcategory',
      'subcategory 2',
      'co2 (t CO₂-eq)',
    ]);
  });

  test('"additional categories" adds commuting, food, waste and construction', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const chart = page.locator('.module-carbon-chart');
    const toggle = chart.locator('.q-checkbox', {
      hasText: 'Show additional estimated categories',
    });
    await expect(toggle).toBeVisible();

    const before = (await exportCsv(page)).slice(1).map((r) => r[0]);
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-checked', 'true');
    const after = (await exportCsv(page)).slice(1).map((r) => r[0]);

    const added = after.filter((c) => !before.includes(c));
    expect([...new Set(added)]).toEqual([
      'Commuting',
      'Food',
      'Waste',
      'Construction and renovation',
    ]);
    expect(after.slice(0, before.length)).toEqual(before);
  });

  test('PNG export matches the displayed chart', async ({ page, context }) => {
    await openExplorer(page, context);
    const chart = page.locator('.module-carbon-chart');
    const canvas = chart.locator('canvas').first();
    await expect(canvas).toBeVisible();
    const displayed = await canvas.evaluate((c: HTMLCanvasElement) => ({
      w: c.width,
      h: c.height,
      url: c.toDataURL('image/png'),
    }));

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      chart.getByRole('button', { name: 'PNG' }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(
      /^module-carbon-footprint-.*\.png$/,
    );
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    const png = Buffer.concat(chunks);
    expect(png.subarray(0, 8)).toEqual(
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    );
    const width = png.readUInt32BE(16);
    const height = png.readUInt32BE(20);
    expect(width).toBe(displayed.w * 2);
    expect(height).toBe(displayed.h * 2);

    const similarity = await page.evaluate(
      async ([exported, shown]) => {
        const load = (src: string) =>
          new Promise<HTMLImageElement>((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = src;
          });
        const [a, b] = await Promise.all([load(exported), load(shown)]);
        const w = 200;
        const h = 100;
        const draw = (img: HTMLImageElement) => {
          const c = document.createElement('canvas');
          c.width = w;
          c.height = h;
          const ctx = c.getContext('2d')!;
          ctx.fillStyle = '#fff';
          ctx.fillRect(0, 0, w, h);
          ctx.drawImage(img, 0, 0, w, h);
          return ctx.getImageData(0, 0, w, h).data;
        };
        const pa = draw(a);
        const pb = draw(b);
        let same = 0;
        let total = 0;
        for (let i = 0; i < pa.length; i += 4) {
          total++;
          const d =
            Math.abs(pa[i] - pb[i]) +
            Math.abs(pa[i + 1] - pb[i + 1]) +
            Math.abs(pa[i + 2] - pb[i + 2]);
          if (d < 60) same++;
        }
        return same / total;
      },
      [`data:image/png;base64,${png.toString('base64')}`, displayed.url],
    );
    expect(similarity).toBeGreaterThan(0.9);
  });

  test('CSV export has the expected columns and values', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const rows = await exportCsv(page);
    expect(rows[0]).toEqual([
      'category',
      'subcategory',
      'subcategory 2',
      'co2 (t CO₂-eq)',
    ]);
    expect(rows.slice(1)).toEqual(
      expect.arrayContaining([
        ['Process emissions', 'co2', '', '1.2'],
        ['Thermal energy emissions', 'combustion', 'natural_gas', '0.8'],
        ['Buildings', 'lighting', 'office', '1.5'],
        ['Buildings', 'lighting', 'laboratories', '1'],
        ['Equipment', 'scientific', '', '2'],
        ['Equipment', 'it', '', '0.7'],
        ['Equipment', 'other', '', '0.3'],
        ['External clouds & AI', 'clouds', 'virtualisation', '0.25'],
        ['External clouds & AI', 'ai', 'provider_openai', '0.15'],
        ['Professional travel', 'train', 'class_2', '1'],
        ['Professional travel', 'plane', 'eco', '4'],
        ['Purchases', 'scientific_equipment', '', '4'],
        ['Purchases', 'it_equipment', '', '2'],
        ['Research facilities', 'research_facilities', '', '0.9'],
      ]),
    );
    expect(rows).toHaveLength(15);
  });

  test('simulation report opens, is readable and consistent with the page', async ({
    page,
    context,
  }) => {
    await openExplorer(page, context);
    const section = await openModule(page, 'Equipment');
    const sub = await openSubmodule(section, 'IT equipments');
    await fillField(sub, 'Name', 'Laptop X');
    await fillField(sub, 'Equipment ID', 'IT-7');
    await pick(sub, 'Class', 'Laptop');
    await fillField(sub, 'Active usage (h/week)', '40');
    await fillField(sub, 'Standby usage (h/week)', '10');
    await clickAdd(sub);
    await expect(subTitle(sub)).toHaveText(/IT equipment \(1\)/);
    const pageTotal = plainNumber(
      await page.locator('.big-number__value').innerText(),
    );

    const [report] = await Promise.all([
      context.waitForEvent('page'),
      page.getByRole('button', { name: 'Download Report' }).click(),
    ]);
    await report.waitForLoadState();
    expect(report.url()).toMatch(/\/en\/10\/2024\/simulation\/explore\/print$/);
    await expect(
      report.getByRole('heading', { name: 'CO₂ Explorer' }),
    ).toBeVisible({ timeout: 15000 });
    await expect(
      report.getByText('Exploration carbon footprint 2024').first(),
    ).toBeVisible();
    expect(
      plainNumber(
        await report.locator('.big-number__value').first().innerText(),
      ),
    ).toBe(pageTotal);
    await expect(report.locator('canvas').first()).toBeVisible();

    for (const label of ISSUE_MODULE_ORDER) {
      await expect(
        report.getByRole('heading', { name: label, exact: true }),
      ).toBeVisible();
    }
    await expect(report.getByText(/IT equipment \(1\)/)).toBeVisible();
    await expect(report.getByText('Laptop X')).toBeVisible();
    await expect(report.getByText('No data available').first()).toBeVisible();

    const overflowing = await report.evaluate(
      () =>
        [...document.querySelectorAll('table')].filter(
          (t) => t.scrollWidth > t.clientWidth + 1,
        ).length,
    );
    expect(overflowing).toBe(0);
  });
});
