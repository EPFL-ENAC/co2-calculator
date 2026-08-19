import { test, expect } from '@playwright/test';

/**
 * Regression test for the #2050 login-submit incident: a first pass at
 * fixing a double-navigation bug in LoginCard.vue removed the button's
 * @click handler on the (wrong) assumption that the form's native submit
 * already covered it. It didn't — the button was `html-type="submit"`,
 * not a real QBtn prop, so it silently rendered as `type="button"` and
 * never submitted the form. That shipped to `dev` and broke every login:
 * clicking the button did nothing at all, with no error anywhere.
 *
 * Only a real click in a real browser catches this — reading the template
 * convinced two reviews (an agent and the author) the old code already
 * worked. This clicks the actual rendered button and asserts the browser
 * actually navigates toward the OAuth login endpoint.
 */
test('clicking the login button navigates to the OAuth login endpoint', async ({
  page,
}) => {
  await page.goto('/');

  const button = page.getByRole('button', { name: /log ?in/i }).first();
  await expect(button).toBeVisible();

  await Promise.all([
    page.waitForURL(/\/api\/v1\/auth\/login/, { timeout: 5000 }),
    button.click(),
  ]);
});
