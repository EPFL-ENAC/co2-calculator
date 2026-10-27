/**
 * Accred outage 2026-10-27: the backend now redirects a callback it cannot
 * finish to /en/login?reason=accred-unavailable instead of a raw JSON 401.
 * The login card must say so, and say nothing for an absent or unknown reason.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import LoginCard from '@/components/organisms/login/LoginCard.vue';
import { loginReasonMessageKey } from '@/utils/loginReason';

test('accred-unavailable shows the banner', async ({ mount }) => {
  const component = await mount(LoginCard, {
    props: { reason: 'accred-unavailable' },
  });

  await expect(component.getByTestId('login-reason')).toContainText(
    'EPFL Accred is unavailable',
  );
});

test('no reason or an unknown one shows no banner', async ({ mount }) => {
  for (const reason of [null, 'bogus']) {
    const component = await mount(LoginCard, { props: { reason } });
    await expect(component.getByTestId('login-reason')).toHaveCount(0);
    await component.unmount();
  }
});

test('reason maps to its message key', () => {
  expect(loginReasonMessageKey('accred-unavailable')).toBe(
    'login_accred_unavailable_message',
  );
  expect(loginReasonMessageKey(null)).toBeNull();
  expect(loginReasonMessageKey('bogus')).toBeNull();
});
