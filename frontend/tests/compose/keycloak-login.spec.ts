import { test, expect } from 'playwright/test';

/**
 * #500: an institution logs in through a generic OIDC provider, without
 * Accred or Entra. The full stack runs with the Keycloak overlay
 * (docker-compose.keycloak.yml), and the roles come from the Keycloak groups
 * claim. This drives the real login and reads the session back.
 */
test('a Keycloak user logs in and gets the role of its group', async ({
  page,
}) => {
  await page.goto('/');
  await page
    .getByRole('button', { name: /log ?in/i })
    .first()
    .click();

  await page.waitForURL(/keycloak\.localhost:8180/);
  await page.getByLabel(/username/i).fill('backoffice-admin');
  await page
    .getByLabel(/password/i)
    .first()
    .fill('backoffice-admin');
  await page.getByRole('button', { name: /sign in/i }).click();

  await page.waitForURL(/^http:\/\/localhost\//);
  const session = await page.request.get('/api/v1/session');
  expect(session.ok()).toBe(true);
  const body = await session.json();
  expect(body.user.email).toBe('backoffice-admin@university.example');
  // The admin group grants the back-office permissions.
  expect(Object.keys(body.user.permissions)).toContain(
    'backoffice.configuration',
  );
});
