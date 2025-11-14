import ky from 'ky';

export const API_BASE_URL = '/api/v1/';

export const api = ky.create({
  prefixUrl: API_BASE_URL,
  credentials: 'include',
  hooks: {
    afterResponse: [
      (request, options, response) => {
        if (response.status === 401 && window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      },
    ],
  },
});
