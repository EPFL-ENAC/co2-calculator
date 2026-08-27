import ky, { type Options } from 'ky';
import { Notify } from 'quasar';
import { i18n } from '@/boot/i18n';
import { captureError, traceparent } from '@/utils/glitchtip';

declare module 'ky' {
  interface Options {
    /** HTTP status codes for which the default error notification should be suppressed */
    skipErrorCodes?: number[];
  }
}
export type ApiOptions = Options;

export const API_BASE_URL = '/api/v1/';
export const API_LOGIN_URL = '/api/v1/auth/login';
export const API_LOGIN_TEST_URL = '/api/v1/auth/login-test';
// All three session verbs hit the same path; the interceptor predicates
// disambiguate by HTTP method (see isRefresh / isSessionCheck below).
export const API_ME_URL = 'session';
export const API_REFRESH_URL = 'session';
export const API_LOGOUT_URL = 'session';
export const loginPageName = '/en/login';

const endsWithSession = (u: string) => /\/session(?:\?.*)?$/.test(u);
const isRefresh = (u: string, m: string) =>
  endsWithSession(u) && m.toUpperCase() === 'POST';
const isSessionCheck = (u: string, m: string) =>
  endsWithSession(u) && m.toUpperCase() === 'GET';

/**
 * Request timeout for every call through this client.
 *
 * ky's own default is **10 s**, and nothing here used to set it — so it was
 * easy to miss that a hard ceiling existed at all. It aborts in the browser
 * regardless of the server still working, which is what #2360 was.
 *
 * **590 s = the OpenShift Route timeout (10 m) minus 10 s.** Deliberately
 * just *under* the router, so on a genuinely stuck request the browser is
 * always the one that gives up first and the failure is attributable: a
 * client abort at ~590 s and a router 504 at 600 s are distinguishable by
 * when they happen. Equal values would collapse them into one symptom.
 *
 * ⚠️ **Coupled to infrastructure.** `haproxy.router.openshift.io/timeout: 10m`
 * is set on the backend Route in all three environments
 * (`epfl/co2-calculator/overlays/{dev,stage,prod}/kustomization.yaml` in the
 * ops repo). If that annotation changes, change this with it — nothing
 * enforces the relationship at build or deploy time.
 *
 * **Applied globally on purpose, not per endpoint.** The first attempt raised
 * it only on the three endpoints with measured cause; a fourth
 * (`carbon-reports/{id}/modules/{m}/{sub}`, #2404) timed out within hours.
 * A hand-maintained list of "known slow" calls is a list that is always out
 * of date, and being wrong means a *user-visible failure on a working
 * backend*. Slowness is a monitoring problem — the latency alerts exist to
 * say "this is too slow"; the client's job is not to guess.
 */
export const REQUEST_TIMEOUT_MS = 590_000;

export const api = ky.create({
  prefixUrl: API_BASE_URL,
  credentials: 'include',
  timeout: REQUEST_TIMEOUT_MS,
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
    beforeRequest: [
      // Propagate the per-navigation trace id so backend OTel spans join the
      // browser's trace — GlitchTip trace_ids become searchable in Tempo (#2372).
      (request) => {
        request.headers.set('traceparent', traceparent());
      },
    ],
    beforeRetry: [
      async ({ request }) => {
        if (!isRefresh(request.url, request.method))
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
          }
          // ⚠️ KNOWN ISSUE: On 401 (expired tokens), this hook used to
          // redirect directly to API_LOGIN_URL (/api/v1/auth/login), which
          // always initiates the Entra OAuth flow — even when the user was
          // logged in as a test user. Redirect to the frontend /login page
          // instead so the user can choose test vs Entra login (issue #949).
          Notify.create({
            color: 'warning',
            message: i18n.global.t('session_expired_notice'),
            position: 'top',
            timeout: 5000,
            actions: [{ icon: 'close', color: 'white' }],
          });
          location.replace(loginPageName);
        } else if (res.status === 403) {
          // Caller declared 403 an expected outcome (skipErrorCodes): skip the
          // toast + hard /unauthorized redirect and let it handle the
          // HTTPError itself (e.g. the unit guard's soft redirect, #2369).
          if (((options as ApiOptions).skipErrorCodes ?? []).includes(403)) {
            return;
          }
          // Parse permission error details from response body
          let permissionDetails: {
            path?: string;
            action?: string;
            message?: string;
          } = {};

          try {
            // Clone the response to read the body without consuming it
            const clonedResponse = res.clone();
            let responseBody: {
              detail?: string | { code?: string };
            } | null = null;

            if (!clonedResponse.bodyUsed) {
              try {
                responseBody = (await clonedResponse.json()) as {
                  detail?: string | { code?: string };
                };
              } catch (jsonError) {
                // Response might not be JSON
                console.warn(
                  'Failed to parse error response as JSON:',
                  jsonError,
                );
              }
            }

            const detail = responseBody?.detail;
            // An object detail (e.g. FIELD_NOT_EDITABLE) is a row-level
            // business denial the caller surfaces itself — not a page-access
            // denial, so no redirect: let ky throw to the caller's catch.
            if (typeof detail === 'object' && detail !== null) {
              return;
            }

            // Extract detail from response body
            const errorDetail =
              typeof detail === 'string' && detail
                ? detail
                : 'Permission denied';

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
          // Capture 5xx in GlitchTip. 4xx is usually client/business-logic
          // (validation, "not found", etc.) and not worth exception noise;
          // 5xx means our backend or infra failed and we want to know.
          // captureError is a fast no-op when no DSN is configured.
          if (res.status >= 500) {
            let body: string | undefined;
            try {
              body = await res.clone().text();
            } catch {
              // Body already consumed elsewhere; not fatal for the report.
            }
            captureError(
              new Error(`HTTP ${res.status} ${req.method} ${req.url}`),
              {
                extra: {
                  status: res.status,
                  statusText: res.statusText,
                  url: req.url,
                  method: req.method,
                  // Truncate to keep events small; full body rarely fits in
                  // GlitchTip's payload limit and isn't usually needed for triage.
                  body: body?.slice(0, 2000),
                },
              },
            );
          }

          const skipCodes = (options as ApiOptions).skipErrorCodes ?? [];
          if (!skipCodes.includes(res.status)) {
            // Surface the backend's error detail when present — the bare status
            // line ("400 Bad Request") doesn't tell the user what to fix.
            let detail: string | undefined;
            try {
              const cloned = res.clone();
              if (!cloned.bodyUsed) {
                const body = (await cloned.json()) as { detail?: unknown };
                if (typeof body?.detail === 'string') {
                  detail = body.detail;
                }
              }
            } catch {
              // Non-JSON body; fall back to the generic status message.
            }
            Notify.create({
              color: 'negative',
              message:
                detail ??
                i18n.global.t('http_error_occurred', {
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

// `typeof import.meta.env !== 'undefined' &&` guards this: this file can be
// loaded by Playwright's component-test collection phase directly in Node,
// without Vite's transform, where `import.meta.env` is plain `undefined` —
// an unguarded `import.meta.env.DEV` throws there.
if (typeof import.meta.env !== 'undefined' && import.meta.env.DEV) {
  window['api'] = api; // Expose for debugging
}
