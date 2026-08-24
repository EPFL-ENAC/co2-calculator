/**
 * #2007 — manual input for Research Facilities and Animal Facilities.
 *
 * The module shipped import-only: every field carried `hideIn: { form: true }`
 * so no form mounted, and the backoffice "deactivate inputs" checkbox was
 * force-locked. These tests pin the delivered behaviour at the UI boundary:
 *
 *  - the facility select reads as acronyms, never as unit codes (the shipped
 *    regression: options were relabelled from a taxonomy keyed on
 *    `researchfacility_id`, so the dropdown was a list of numbers);
 *  - selecting a facility mirrors its unit in, read-only, because the emission
 *    formula only resolves when the entry's unit equals the factor's;
 *  - `use` is bounded by that unit (0-100 for %, whole numbers for housings);
 *  - the backoffice switch hides the form behind a notice.
 */
import { test, expect, type Page } from '@playwright/test';
import {
  RF_URL,
  mockResearchFacilitiesBackend,
  type RfMockOptions,
} from './setup/research-facilities-mocks';

const COMMON_TABLE = 'Research facilities';
const ANIMAL_TABLE = 'Rodent and fish animal facilities';

async function openModule(page: Page, options: RfMockOptions = {}) {
  await mockResearchFacilitiesBackend(page, options);
  await page.goto(RF_URL);
  await expect(page.getByText(COMMON_TABLE).first()).toBeVisible();
}

/** The submodule sections are collapsed until their header is clicked. */
async function expandSection(page: Page, title: string) {
  const header = page.locator('.q-expansion-item').filter({ hasText: title });
  await header.first().click();
}

function facilitySelect(page: Page, section: string) {
  return page
    .locator('.q-expansion-item')
    .filter({ hasText: section })
    .locator('.q-field')
    .filter({ hasText: 'Research facility' })
    .first();
}

async function openFacilityOptions(page: Page, section: string) {
  await facilitySelect(page, section).click();
  await expect(page.locator('.q-menu .q-item').first()).toBeVisible();
}

test.describe('#2007 research facilities manual input', () => {
  test('facility options read as acronyms, not unit codes', async ({
    page,
  }) => {
    await openModule(page);
    await expandSection(page, COMMON_TABLE);
    await openFacilityOptions(page, COMMON_TABLE);

    const options = page.locator('.q-menu .q-item');
    await expect(options.filter({ hasText: 'SCITAS-GE' })).toHaveCount(1);
    await expect(options.filter({ hasText: 'CAM-GE' })).toHaveCount(1);

    // The regression: `researchfacility_id` is what the option submits, and it
    // must never be what the option shows.
    const labels = await options.allInnerTexts();
    for (const id of ['1902', '0872', '0619']) {
      expect(labels.join('|')).not.toContain(id);
    }
  });

  test('options keep their acronyms when the taxonomy is unavailable', async ({
    page,
  }) => {
    // The labels come from the factor catalog, not the taxonomy — a taxonomy
    // that fails to load must not silently turn the dropdown back into codes.
    await openModule(page, { taxonomyUnavailable: true });
    await expandSection(page, COMMON_TABLE);
    await openFacilityOptions(page, COMMON_TABLE);

    await expect(
      page.locator('.q-menu .q-item').filter({ hasText: 'SCITAS-GE' }),
    ).toHaveCount(1);
  });

  test('options are sorted by acronym', async ({ page }) => {
    // ~90 platforms come back in DB order; an unsorted picker is unusable.
    await openModule(page);
    await expandSection(page, COMMON_TABLE);
    await openFacilityOptions(page, COMMON_TABLE);

    const labels = (await page.locator('.q-menu .q-item').allInnerTexts()).map(
      (t) => t.trim(),
    );
    expect(labels).toEqual([...labels].sort((a, b) => a.localeCompare(b)));
  });

  test('picking a facility mirrors its unit into a read-only field', async ({
    page,
  }) => {
    await openModule(page);
    await expandSection(page, COMMON_TABLE);
    await openFacilityOptions(page, COMMON_TABLE);
    await page.locator('.q-menu .q-item').filter({ hasText: 'CAM-GE' }).click();

    const unit = page
      .locator('.q-expansion-item')
      .filter({ hasText: COMMON_TABLE })
      .locator('.q-field')
      .filter({ hasText: 'Unit' })
      .locator('input')
      .first();
    await expect(unit).toHaveValue('%');
    // Never typed: a unit that disagrees with the factor's makes the emission
    // formula raise, so the entry would 422 on save.
    await expect(unit).toHaveAttribute('readonly', '');
  });

  test('use above 100 is refused when the unit is a percentage', async ({
    page,
  }) => {
    const created: Record<string, unknown>[] = [];
    await openModule(page, { created });
    await expandSection(page, COMMON_TABLE);
    await openFacilityOptions(page, COMMON_TABLE);
    await page.locator('.q-menu .q-item').filter({ hasText: 'CAM-GE' }).click();

    const section = page
      .locator('.q-expansion-item')
      .filter({ hasText: COMMON_TABLE });
    await section
      .locator('.q-field')
      .filter({ hasText: 'Use' })
      .locator('input')
      .first()
      .fill('150');
    await section.getByRole('button', { name: 'Add', exact: true }).click();

    await expect(section.getByText('Must be at most 100')).toBeVisible();
    expect(created).toHaveLength(0);
  });

  test('a whole-number use is accepted for a percentage facility', async ({
    page,
  }) => {
    const created: Record<string, unknown>[] = [];
    await openModule(page, { created });
    await expandSection(page, COMMON_TABLE);
    await openFacilityOptions(page, COMMON_TABLE);
    await page.locator('.q-menu .q-item').filter({ hasText: 'CAM-GE' }).click();

    const section = page
      .locator('.q-expansion-item')
      .filter({ hasText: COMMON_TABLE });
    await section
      .locator('.q-field')
      .filter({ hasText: 'Use' })
      .locator('input')
      .first()
      .fill('40');
    await section.getByRole('button', { name: 'Add', exact: true }).click();

    await expect.poll(() => created.length).toBe(1);
    // The id is what identifies the factor; the name rides along mirrored.
    expect(created[0]).toMatchObject({
      researchfacility_id: '0872',
      researchfacility_name: 'CAM-GE',
      use: 40,
      use_unit: '%',
    });
  });

  test('animal facilities offer housing types for the picked facility', async ({
    page,
  }) => {
    await openModule(page);
    await expandSection(page, ANIMAL_TABLE);
    await openFacilityOptions(page, ANIMAL_TABLE);
    await page.locator('.q-menu .q-item').filter({ hasText: 'CPG' }).click();

    const section = page
      .locator('.q-expansion-item')
      .filter({ hasText: ANIMAL_TABLE });
    await section
      .locator('.q-field')
      .filter({ hasText: 'Type' })
      .first()
      .click();

    // Translated through the module's own `type.{value}` keys, not raw
    // factor values.
    const options = page.locator('.q-menu .q-item');
    await expect(options.filter({ hasText: 'Rodents' })).toHaveCount(1);
    await expect(options.filter({ hasText: 'Fish' })).toHaveCount(1);
  });

  test('fractional housings are refused', async ({ page }) => {
    const created: Record<string, unknown>[] = [];
    await openModule(page, { created });
    await expandSection(page, ANIMAL_TABLE);
    await openFacilityOptions(page, ANIMAL_TABLE);
    await page.locator('.q-menu .q-item').filter({ hasText: 'CPG' }).click();

    const section = page
      .locator('.q-expansion-item')
      .filter({ hasText: ANIMAL_TABLE });
    await section
      .locator('.q-field')
      .filter({ hasText: 'Type' })
      .first()
      .click();
    await page
      .locator('.q-menu .q-item')
      .filter({ hasText: 'Rodents' })
      .click();
    await section
      .locator('.q-field')
      .filter({ hasText: 'Number of housing' })
      .locator('input')
      .first()
      .fill('2.5');
    await section.getByRole('button', { name: 'Add', exact: true }).click();

    await expect(section.getByText('Must be a whole number')).toBeVisible();
    expect(created).toHaveLength(0);
  });

  test('the backoffice switch replaces the form with a notice', async ({
    page,
  }) => {
    await openModule(page, { inputsDeactivated: true });
    await expandSection(page, COMMON_TABLE);

    const section = page
      .locator('.q-expansion-item')
      .filter({ hasText: COMMON_TABLE });
    await expect(section.locator('.inputs-deactivated-notice')).toBeVisible();
    await expect(
      section.getByRole('button', { name: 'Add', exact: true }),
    ).toHaveCount(0);
  });
});
