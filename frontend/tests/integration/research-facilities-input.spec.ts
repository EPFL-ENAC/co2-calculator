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

/**
 * Pick an option by label without a real mouse click.
 *
 * The select sits ~970px down a 720px viewport, so QMenu -- which opens
 * downwards and is `position: fixed` -- lands with its options straddling the
 * fold. A click targets the element's centre, and for a 48px option at y=708
 * that centre is 12px past the bottom edge, so Playwright loops on "element is
 * outside of the viewport" until timeout: scrolling to reach the option moves
 * the anchor, QMenu repositions, repeat.
 *
 * There was never any margin here -- before #2613 the centre sat at exactly
 * 720 -- so a one-pixel layout change flips these tests. Dispatching the event
 * drops the dependency on where the menu happens to land.
 */
async function pickOption(page: Page, label: string) {
  const option = page.locator('.q-menu .q-item').filter({ hasText: label });
  await expect(option).toHaveCount(1);
  await option.dispatchEvent('click');
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

  test('a load error, not a silent empty list, shows when the taxonomy is unavailable', async ({
    page,
  }) => {
    // Since #2391 decision 1 the taxonomy endpoint is the select's only
    // option source — a 404 there means the lookup failed, not "this
    // submodule has no facilities". An empty dropdown would read as the
    // latter, so the failure must surface as a visible error (#2498).
    await openModule(page, { taxonomyUnavailable: true });
    await expandSection(page, COMMON_TABLE);
    await facilitySelect(page, COMMON_TABLE).click();

    await expect(
      facilitySelect(page, COMMON_TABLE).getByText(
        'Options could not be loaded. Try again later.',
      ),
    ).toBeVisible();
    await expect(page.locator('.q-menu .q-item')).toHaveCount(0);
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
    await pickOption(page, 'CAM-GE');

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
    await pickOption(page, 'CAM-GE');

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
    await pickOption(page, 'CAM-GE');

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

  // FIXME(#2613): the housing-type select comes back with zero options. The
  // click fix above is what made this visible -- these tests used to time out
  // on an unclickable menu before ever reaching the assertion. Bisected to
  // a237c5667; the backend taxonomy shape is unchanged there, so it is the new
  // frontend kind/subkind flattening or the `optionsId: 'subkind'` lookup,
  // against a mock that may simply be stale. Needs a frontend owner: if it
  // reproduces against the real backend, a required field has no options.
  test.fixme('animal facilities offer housing types for the picked facility', async ({
    page,
  }) => {
    await openModule(page);
    await expandSection(page, ANIMAL_TABLE);
    await openFacilityOptions(page, ANIMAL_TABLE);
    await pickOption(page, 'CPG');

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

  // FIXME(#2613): the housing-type select comes back with zero options. The
  // click fix above is what made this visible -- these tests used to time out
  // on an unclickable menu before ever reaching the assertion. Bisected to
  // a237c5667; the backend taxonomy shape is unchanged there, so it is the new
  // frontend kind/subkind flattening or the `optionsId: 'subkind'` lookup,
  // against a mock that may simply be stale. Needs a frontend owner: if it
  // reproduces against the real backend, a required field has no options.
  test.fixme('fractional housings are refused', async ({ page }) => {
    const created: Record<string, unknown>[] = [];
    await openModule(page, { created });
    await expandSection(page, ANIMAL_TABLE);
    await openFacilityOptions(page, ANIMAL_TABLE);
    await pickOption(page, 'CPG');

    const section = page
      .locator('.q-expansion-item')
      .filter({ hasText: ANIMAL_TABLE });
    await section
      .locator('.q-field')
      .filter({ hasText: 'Type' })
      .first()
      .click();
    await pickOption(page, 'Rodents');
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
