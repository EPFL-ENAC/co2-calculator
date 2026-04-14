import ky from 'ky';
import { Notify } from 'quasar';

export const API_BASE_URL = '/api/v1/';
export const API_LOGIN_URL = '/api/v1/auth/login';
export const API_LOGIN_TEST_URL = '/api/v1/auth/login-test';
export const API_ME_URL = 'auth/me';
export const API_REFRESH_URL = 'auth/refresh';
export const API_LOGOUT_URL = 'auth/logout';
export const loginPageName = '/en/login';

const isRefresh = (u: string) => u.endsWith(API_REFRESH_URL);

export const api = ky.create({
  prefixUrl: API_BASE_URL,
  credentials: 'include',
  retry: { limit: 1, statusCodes: [401] },
  hooks: {
    beforeRetry: [
      // For any non-refresh call, try to refresh before retrying
      async ({ request }) => {
        if (!isRefresh(request.url))
          // do not retry 'refresh' itself
          await api.post(API_REFRESH_URL, { retry: { limit: 0 } });
      },
    ],
    afterResponse: [
      async (req, options, res) => {
        if (res.status === 401 && !isRefresh(req.url)) {
          // If still 401 after refresh, redirect to login
          const isSessionCheck = req.url.endsWith(API_ME_URL);
          if (isSessionCheck) {
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
            location.replace(loginPageName);
          }
        }
        if (res.status === 403) {
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
        }
      },
    ],
  },
});

if (process.env.NODE_ENV === 'development') {
  window['api'] = api; // Expose for debugging
}
