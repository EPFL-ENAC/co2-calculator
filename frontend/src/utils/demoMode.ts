// Demo-instance switch (APP_DEMO_MODE). Only the literal "true" turns it on,
// so an unset, empty or mistyped value keeps the app usable.
export function isDemoMode(raw: string | false | undefined): boolean {
  return typeof raw === 'string' && raw.trim().toLowerCase() === 'true';
}

// "Continue to the demo anyway" is remembered for the browser tab session, so
// the OAuth login round-trip (a full page reload) doesn't bring the notice
// back. Storage can be unavailable (private mode, blocked site data): then the
// notice simply shows again on the next load.
const DISMISSED_KEY = 'co2-demo-notice-dismissed';

export function isDemoNoticeDismissed(): boolean {
  try {
    return sessionStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

export function dismissDemoNotice(): void {
  try {
    sessionStorage.setItem(DISMISSED_KEY, '1');
  } catch {
    // Not persisted; the in-memory dismissal in App.vue still applies.
  }
}
