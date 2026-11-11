import { test, expect } from './setup/test';

test('homepage loads', async ({ page }) => {
  await page.goto('/'); // Uses baseURL automatically
  // The institution boot file sets the title, so wait for it.
  await expect(page).toHaveTitle('EPFL CO2 Calculator');
});
