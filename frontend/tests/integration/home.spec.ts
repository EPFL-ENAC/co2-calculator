import { test, expect } from './setup/test';

test('homepage loads', async ({ page }) => {
  await page.goto('/'); // Uses baseURL automatically
  expect(await page.title()).toBe('EPFL CO2 Calculator');
});
