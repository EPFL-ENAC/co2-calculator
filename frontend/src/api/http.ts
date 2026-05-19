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
export const API_LOGIN_URL = '/api/v1/auth/login';
export const API_LOGIN_TEST_URL = '/api/v1/auth/login-test';
export const API_ME_URL = 'auth/me';
export const API_CSRF_URL = 'auth/csrf';
export const API_REFRESH_URL = 'auth/refresh';
export const API_LOGOUT_URL = 'auth/logout';
export const loginPageName = '/en/login';
export const CSRF_HEADER_NAME = 'X-CSRF';

type CsrfBootstrapResponse = {
  csrf_enabled: boolean;
  csrf_token: string | null;
};

const isRefresh = (u: string) => u.endsWith(API_REFRESH_URL);
const isCsrfBootstrap = (u: string) => u.endsWith(API_CSRF_URL);
const CSRF_METHODS = new Set(['POST', 'PUT', 'DELETE', 'PATCH']);

let csrfToken: string | null = null;
let csrfBootstrapPromise: Promise<string | null> | null = null;
let csrfEnabled: boolean | null = null;

const apiNoHooks = ky.create({
  prefixUrl: API_BASE_URL,
  credentials: 'include',
  retry: { limit: 0 },
});

async function fetchAndStoreCsrfToken(): Promise<string | null> {
  if (csrfBootstrapPromise) {
    return csrfBootstrapPromise;
  }

  csrfBootstrapPromise = (async () => {
    const response = await apiNoHooks
      .get(API_CSRF_URL)
      .json<CsrfBootstrapResponse>();
    csrfEnabled = response.csrf_enabled;
    csrfToken = response.csrf_enabled ? response.csrf_token : null;
    return csrfToken;
  })();

  try {
    return await csrfBootstrapPromise;
  } finally {
    csrfBootstrapPromise = null;
  }
}

async function ensureCsrfToken(): Promise<string | null> {
  if (csrfEnabled === true && csrfToken) {
    return csrfToken;
  }

  if (csrfEnabled === false) {
    return null;
  }

  try {
    return await fetchAndStoreCsrfToken();
  } catch {
    return null;
  }
}

export async function bootstrapCsrfToken(): Promise<string | null> {
  return fetchAndStoreCsrfToken();
}

export function clearCsrfToken(): void {
  csrfToken = null;
  csrfEnabled = null;
  csrfBootstrapPromise = null;
}

async function handleCsrfError(
  req: Request,
  options: RequestInit,
): Promise<Response | undefined> {
  const newToken = await bootstrapCsrfToken();
  if (!newToken) {
    location.replace(loginPageName);
    return;
  }

  const headers = new Headers(options.headers ?? req.headers);
  headers.set(CSRF_HEADER_NAME, newToken);

  try {
    return await apiNoHooks(req.url, {
      method: options.method ?? req.method,
      body: options.body ?? req.body,
      headers,
      credentials: 'include',
      retry: { limit: 0 },
    });
  } catch (error) {
    console.warn('CSRF retry failed:', error);
    location.replace(loginPageName);
    return;
  }
}

async function handlePermissionError(
  _res: Response,
  errorResponse: {
    error?: string;
    detail?: string;
    reason?: string;
  } | null,
): Promise<void> {
  let permissionDetails: {
    path?: string;
    action?: string;
    message?: string;
  };

  const errorDetail = errorResponse?.detail || 'Permission denied';

  const permissionDeniedMatch = errorDetail.match(/Permission denied:\s*(.+)/i);
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

  const queryParams = new URLSearchParams();
  if (permissionDetails.path) {
    queryParams.set('permission', permissionDetails.path);
  }
  if (permissionDetails.action) {
    queryParams.set('action', permissionDetails.action);
  }

  const toastMessage = permissionDetails.message || 'Access denied';
  Notify.create({
    color: 'negative',
    message: toastMessage,
    position: 'top',
    timeout: 3000,
    actions: [{ icon: 'close', color: 'white' }],
  });

  const queryString = queryParams.toString();
  const redirectUrl = queryString
    ? `/unauthorized?${queryString}`
    : '/unauthorized';
  location.replace(redirectUrl);
}

function updateCsrfToken(token: string): void {
  csrfToken = token;
  csrfEnabled = true;
}

export function updateCsrfDisabled(): void {
  csrfToken = null;
  csrfEnabled = false;
}

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
    beforeRequest: [
      async (request) => {
        if (isCsrfBootstrap(request.url)) {
          return;
        }

        if (!CSRF_METHODS.has(request.method.toUpperCase())) {
          return;
        }

        const token = await ensureCsrfToken();
        if (token) {
          request.headers.set(CSRF_HEADER_NAME, token);
        }
      },
    ],
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
        // Extract CSRF token from refresh response
        if (isRefresh(req.url) && res.status === 200) {
          try {
            const data = (await res.clone().json()) as {
              csrf_token?: string | null;
            };
            if (typeof data.csrf_token === 'string') {
              updateCsrfToken(data.csrf_token);
            } else if (data.csrf_token === null) {
              updateCsrfDisabled();
            }
          } catch {
            // Ignore JSON parse errors
          }
        }

        if (res.status === 401) {
          if (isRefresh(req.url)) {
            // If refresh returns 401, let it pass through and be handled by
            // next api call, which will trigger the login redirect. This prevents infinite
            // loops in case the refresh token is also expired or invalid.
            return;
          }
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
        }
        if (res.status === 403) {
          let errorResponse: {
            error?: string;
            detail?: string;
            reason?: string;
          } | null = null;

          try {
            const clonedResponse = res.clone();
            if (!clonedResponse.bodyUsed) {
              try {
                errorResponse = (await clonedResponse.json()) as {
                  error?: string;
                  detail?: string;
                  reason?: string;
                };
              } catch (jsonError) {
                console.warn(
                  'Failed to parse error response as JSON:',
                  jsonError,
                );
              }
            }
          } catch (parseError) {
            console.warn('Failed to parse error response:', parseError);
          }

          if (errorResponse?.error === 'csrf_validation_failed') {
            return await handleCsrfError(req, options);
          } else {
            await handlePermissionError(res, errorResponse);
          }
        }
      },
    ],
  },
});

if (process.env.NODE_ENV === 'development') {
  window['api'] = api; // Expose for debugging
}
