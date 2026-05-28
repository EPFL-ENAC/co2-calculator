import ky, { type Options } from 'ky';
import { Notify } from 'quasar';
import { i18n } from 'src/boot/i18n';

declare module 'ky' {
  interface Options {
    /** HTTP status codes for which the default error notification should be suppressed */
    skipErrorCodes?: number[];
  }
}
export type ApiOptions = Options;

export const API_BASE_URL = '/api/v1/';
export const API_LOGIN_URL = '/api/v1/oauth/login';
export const API_LOGIN_TEST_URL = '/api/v1/oauth/login-test';
// All three session verbs hit the same path; the interceptor predicates
// disambiguate by HTTP method (see isRefresh / isSessionCheck below).
export const API_ME_URL = 'session';
export const API_REFRESH_URL = 'session';
export const API_LOGOUT_URL = 'session';
export const API_EXCHANGE_URL = 'session/exchange';
export const loginPageName = '/en/login';

const endsWithSession = (u: string) => /\/session(?:\?.*)?$/.test(u);
const isRefresh = (u: string, m: string) =>
  endsWithSession(u) && m.toUpperCase() === 'POST';
const isSessionCheck = (u: string, m: string) =>
  endsWithSession(u) && m.toUpperCase() === 'GET';

export const api = ky.create({
  prefixUrl: API_BASE_URL,
  credentials: 'include',
  // ky's default `methods` excludes POST/PATCH, so without overriding it the
  // beforeRetry hook below would never fire on form submits — users mid-edit
  // would get bounced to /login on a single 401 even though the refresh
  // cookie was still valid (issue #949).
  retry: {
    limit: 1,
    statusCodes: [401],
    methods: ['get', 'put', 'post', 'patch', 'head', 'delete', 'options'],
  },
  hooks: {
    beforeRetry: [
      // For any non-refresh call, try to refresh before retrying
      async ({ request }) => {
        if (!isRefresh(request.url, request.method))
          // do not retry 'refresh' itself
          await api.post(API_REFRESH_URL, { retry: { limit: 0 } });
      },
    ],
    afterResponse: [
      async (req, options, res) => {
        if (res.status === 401) {
          if (isRefresh(req.url, req.method)) {
            // If refresh returns 401, let it pass through and be handled by
            // next api call, which will trigger the login redirect. This prevents infinite
            // loops in case the refresh token is also expired or invalid.
            return;
          }
          // If still 401 after refresh, redirect to login
          if (isSessionCheck(req.url, req.method)) {
            // For session check, do not redirect, just return
            // This prevents redirect loops during session validation
            // vue Router guard will handle the redirection
            return;
          } else {
            // ⚠️ KNOWN ISSUE: On 401 (expired tokens), this hook used to
            // redirects directly to
            // API_LOGIN_URL (/api/v1/auth/login), which always initiates the Entra OAuth
            // flow — even when the user was logged in as a test user.
            //
            // If the Entra SSO session is still active (e.g. only local cookies were
            // cleared, not a real Entra logout), the user gets silently re-authenticated
            // as their Entra identity, overwriting the test session.
            //
            // Redirect to the frontend /login page instead, so the user can
            // explicitly choose test vs Entra login.
            // may induced infinite redirect loops if the login page itself makes API calls
            // that return 401, but in practice this should not happen since the login page
            // should not make authenticated API calls.
            //
            // Surface a toast before navigating so the user understands why
            // they're being kicked out (issue #949: previously a silent
            // bounce to /login that looked like the form had submitted them
            // back to the home page).
            Notify.create({
              color: 'warning',
              message: i18n.global.t('session_expired_notice'),
              position: 'top',
              timeout: 5000,
              actions: [{ icon: 'close', color: 'white' }],
            });
            location.replace(loginPageName);
          }
        } else if (res.status === 403) {
          // Parse permission error details from response body
          let permissionDetails: {
            path?: string;
            action?: string;
            message?: string;
          } = {};

          try {
            // Clone the response to read the body without consuming it
            const clonedResponse = res.clone();
            let responseBody: { detail?: string } | null = null;

            if (!clonedResponse.bodyUsed) {
              try {
                responseBody = (await clonedResponse.json()) as {
                  detail?: string;
                };
              } catch (jsonError) {
                // Response might not be JSON
                console.warn(
                  'Failed to parse error response as JSON:',
                  jsonError,
                );
              }
            }

            // Extract detail from response body
            const errorDetail = responseBody?.detail || 'Permission denied';

            // Try to parse permission path and action from error message
            // Pattern: "Permission denied: {path}.{action} required"
            const permissionDeniedMatch = errorDetail.match(
              /Permission denied:\s*(.+)/i,
            );
            if (permissionDeniedMatch) {
              const reasonText = permissionDeniedMatch[1].trim();
              const pathActionMatch = reasonText.match(
                /^([a-z0-9_.]+)\.([a-z]+)\s+required$/i,
              );
              if (pathActionMatch) {
                permissionDetails = {
                  path: pathActionMatch[1],
                  action: pathActionMatch[2],
                  message: errorDetail,
                };
              } else {
                permissionDetails = {
                  message: errorDetail,
                };
              }
            } else {
              permissionDetails = {
                message: errorDetail,
              };
            }
          } catch (parseError) {
            console.warn('Failed to parse permission error:', parseError);
          }

          // Build query params for the unauthorized page
          const queryParams = new URLSearchParams();
          if (permissionDetails.path) {
            queryParams.set('permission', permissionDetails.path);
          }
          if (permissionDetails.action) {
            queryParams.set('action', permissionDetails.action);
          }

          // Show toast notification before redirecting
          const toastMessage = permissionDetails.message || 'Access denied';
          Notify.create({
            color: 'negative',
            message: toastMessage,
            position: 'top',
            timeout: 3000,
            actions: [{ icon: 'close', color: 'white' }],
          });

          // Redirect immediately - toast will remain visible during navigation
          const queryString = queryParams.toString();
          const redirectUrl = queryString
            ? `/unauthorized?${queryString}`
            : '/unauthorized';
          location.replace(redirectUrl);
        } else if (!res.ok) {
          // Capture 5xx in Sentry. 4xx is usually client/business-logic
          // (validation, "not found", etc.) and not worth exception noise;
          // 5xx means our backend or infra failed and we want to know.
          //
          // Dynamic import so the @sentry/vue chunk stays lazy (the boot
          // file uses dynamic import too — see boot/sentry.ts). On the first
          // 5xx of a session this incurs one async chunk load; subsequent
          // captures hit cache. A fast no-op when no DSN is configured.
          if (res.status >= 500) {
            let body: string | undefined;
            try {
              body = await res.clone().text();
            } catch {
              // Body already consumed elsewhere; not fatal for the report.
            }
            void import('@sentry/vue').then(({ captureMessage }) => {
              captureMessage(`HTTP ${res.status} ${req.method} ${req.url}`, {
                level: 'error',
                extra: {
                  status: res.status,
                  statusText: res.statusText,
                  url: req.url,
                  method: req.method,
                  // Truncate to keep events small; full body rarely fits in
                  // GlitchTip's payload limit and isn't usually needed for
                  // triage.
                  body: body?.slice(0, 2000),
                },
              });
            });
          }

          const skipCodes = (options as ApiOptions).skipErrorCodes ?? [];
          if (!skipCodes.includes(res.status)) {
            // For other errors, show a generic error toast
            Notify.create({
              color: 'negative',
              message: i18n.global.t('http_error_occurred', {
                status: res.status,
                text: res.statusText,
              }),
              position: 'top',
              timeout: 3000,
              actions: [{ icon: 'close', color: 'white' }],
            });
          }
        }
      },
    ],
  },
});

if (process.env.NODE_ENV === 'development') {
  window['api'] = api; // Expose for debugging
}
