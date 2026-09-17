/**
 * #2818 — the calculator layout must fit a laptop-sized viewport.
 *
 * The module navigation bar carried a fixed 1320px width. As the widest item
 * of the module page's auto-sized grid column it forced that column to 1320px,
 * so every card on the page stretched with it and the right edge was clipped
 * behind the content pane on 13"–14" laptops. The header title was also
 * truncated because a spacer split the toolbar's free space with it.
 *
 * Two auto-sized grid columns (the page grid and the submodule list) let a
 * wide data table's minimum width push the cards out the same way once a
 * section was expanded; those tables must scroll inside their own container.
 */
import { test, expect, type Page } from '@playwright/test';
import {
  RF_URL,
  mockResearchFacilitiesBackend,
} from './setup/research-facilities-mocks';

const LAPTOP = { width: 1024, height: 768 };

async function openModule(page: Page) {
  await mockResearchFacilitiesBackend(page);
  await page.goto(RF_URL);
  await expect(page.getByText('Research facilities').first()).toBeVisible();
}

/** The submodule sections are collapsed until their header is clicked. */
async function expandAllSections(page: Page) {
  const headers = page.locator(
    '.q-expansion-item:not(.q-expansion-item--expanded) > .q-expansion-item__container > .q-item',
  );
  // The locator re-indexes as sections open, so always take the first one.
  for (let left = await headers.count(); left > 0; left -= 1) {
    await headers.first().click();
    await expect(headers).toHaveCount(left - 1);
  }
  await expect(page.locator('.q-table').first()).toBeVisible();
}

function overflow(page: Page, selector: string) {
  return page
    .locator(selector)
    .first()
    .evaluate((el) => el.scrollWidth - el.clientWidth);
}

test.describe('laptop viewport layout (#2818)', () => {
  test.use({ viewport: LAPTOP });

  test('the module page fits the content pane without horizontal overflow', async ({
    page,
  }) => {
    await openModule(page);
    expect(await overflow(page, '.content-wrapper')).toBe(0);
  });

  test('expanded data tables scroll inside their section instead of widening the page', async ({
    page,
  }) => {
    await openModule(page);
    await expandAllSections(page);
    expect(await overflow(page, '.content-wrapper')).toBe(0);
    const paneWidth = await page
      .locator('.content-wrapper')
      .evaluate((el) => el.clientWidth);
    for (const card of await page.locator('.page-grid > *').all()) {
      expect(await card.evaluate((el) => el.scrollWidth)).toBeLessThanOrEqual(
        paneWidth,
      );
    }
  });

  test('the module page keeps a gutter between the sidebar and its cards', async ({
    page,
  }) => {
    await openModule(page);
    const gutter = await page
      .locator('.page-grid')
      .first()
      .evaluate((grid) => {
        const pane = grid.closest('.content-wrapper') as HTMLElement;
        const card = grid.firstElementChild as HTMLElement;
        return (
          card.getBoundingClientRect().left - pane.getBoundingClientRect().left
        );
      });
    expect(gutter).toBeGreaterThanOrEqual(16);
  });

  test('the header title is not truncated', async ({ page }) => {
    await openModule(page);
    expect(await overflow(page, '.q-toolbar__title')).toBe(0);
  });
});
