/**
 * Issue #2443 — Home chart icon-axis greying rules. An icon is:
 *  - hidden ⇔ its module is deactivated in the back-office config;
 *  - greyed out ⇔ the user lacks view/edit access to the module;
 *  - clickable otherwise — module status (validated or not) and data
 *    presence never grey an icon.
 * Scenario data lives in ``setup/home-module-visibility-mocks.ts``.
 */
import { test, expect, type Page } from '@playwright/test';
import { HOME_URL, mockHomeBackend } from './setup/home-module-visibility-mocks';

// The icon axis renders one `.module-icon-axis__item` per bar: a
// `router-link` (anchor) when enabled, a plain `div` with the
// `--disabled` modifier when greyed out. Labels are the translated
// category names (English locale via HOME_URL).
function iconItem(page: Page, label: string) {
  return page.locator('.module-icon-axis__item').filter({
    has: page.locator('.module-icon-axis__label', {
      hasText: new RegExp(`^${label}$`),
    }),
  });
}

test.describe('home chart — module icon greying (#2443)', () => {
  test.beforeEach(async ({ page }) => {
    await mockHomeBackend(page);
    await page.goto(HOME_URL);
    await expect(page.locator('.module-icon-axis__item').first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('a validated module with no computed stats is clickable, not greyed out', async ({
    page,
  }) => {
    const cloud = iconItem(page, 'External clouds & AI');
    await expect(cloud).toHaveClass(/module-icon-axis__item--link/);
    await expect(cloud).not.toHaveClass(/module-icon-axis__item--disabled/);
  });

  test('a not-started module the user can access is clickable, not greyed out', async ({
    page,
  }) => {
    const purchases = iconItem(page, 'Purchases');
    await expect(purchases).toHaveClass(/module-icon-axis__item--link/);
    await expect(purchases).not.toHaveClass(/module-icon-axis__item--disabled/);

    // Sanity: a validated module WITH stats is clickable too.
    await expect(iconItem(page, 'Equipment')).toHaveClass(
      /module-icon-axis__item--link/,
    );
  });

  test('a module the user cannot access is greyed out even when validated with stats', async ({
    page,
  }) => {
    const travel = iconItem(page, 'Professional travel');
    await expect(travel).toHaveClass(/module-icon-axis__item--disabled/);
    // Greyed icons are inert divs, never links.
    await expect(travel).not.toHaveAttribute('href', /.+/);
  });

  test('a back-office-disabled module is absent from the chart entirely', async ({
    page,
  }) => {
    await expect(iconItem(page, 'Process emissions')).toHaveCount(0);
  });
});
