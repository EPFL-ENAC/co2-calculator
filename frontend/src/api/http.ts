import ky from 'ky';

export const API_BASE_URL = '/api/v1/';
export const API_LOGIN_URL = '/api/v1/auth/login';
export const API_REFRESH_URL = 'auth/refresh';

const isRefresh = (u: string) => u.endsWith(API_REFRESH_URL);

export const api = ky.create({
  prefixUrl: API_BASE_URL,
  credentials: 'include',
  retry: { limit: 1, statusCodes: [401] },
  hooks: {
    beforeRetry: [
      async ({ request }) => {
        if (!isRefresh(request.url))
          await api.post(API_REFRESH_URL, { retry: { limit: 0 } });
      },
    ],
    afterResponse: [
      (req, _o, res) => {
        if (res.status === 401 && !isRefresh(req.url))
          location.replace(API_LOGIN_URL);
      },
    ],
  },
});
