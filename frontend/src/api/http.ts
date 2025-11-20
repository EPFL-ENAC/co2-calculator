import ky from 'ky';

export const API_BASE_URL = '/api/v1/';
export const API_LOGIN_URL = '/api/v1/auth/login';
export const API_ME_URL = 'auth/me';
export const API_REFRESH_URL = 'auth/refresh';
export const API_LOGOUT_URL = 'auth/logout';

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
      (req, _o, res) => {
        if (res.status === 401 && !isRefresh(req.url)) {
          // If still 401 after refresh, redirect to login
          const isSessionCheck = req.url.endsWith(API_ME_URL);
          if (isSessionCheck) {
            // For session check, do not redirect, just return
            // This prevents redirect loops during session validation
            // vue Router guard will handle the redirection
            return;
          } else {
            // GOING into oauth2 login flow
            location.replace(API_LOGIN_URL);
          }
        }
      },
    ],
  },
});

if (process.env.NODE_ENV === 'development') {
  window['api'] = api; // Expose for debugging
}
