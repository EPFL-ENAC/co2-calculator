/**
 * Pure helper for the login page banner: the backend redirects an OAuth
 * callback it cannot finish to /<lang>/login?reason=<reason>. Kept free of
 * store/i18n imports so it stays unit-testable without mounting Vue.
 */

/** Accred (api.epfl.ch) failed during the callback; the user can only retry later. */
export type LoginReason = 'accred-unavailable';

const LOGIN_REASON_MESSAGE_KEYS: Record<LoginReason, string> = {
  'accred-unavailable': 'login_accred_unavailable_message',
};

function isLoginReason(reason: string): reason is LoginReason {
  return reason in LOGIN_REASON_MESSAGE_KEYS;
}

/** i18n key for a known `?reason=`, or `null` when absent or unrecognised. */
export function loginReasonMessageKey(reason: string | null): string | null {
  if (reason !== null && isLoginReason(reason)) {
    return LOGIN_REASON_MESSAGE_KEYS[reason];
  }
  return null;
}
