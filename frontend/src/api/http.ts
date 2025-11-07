import ky from 'ky';

export const api = ky.create({
  prefixUrl: '/api/v1/',
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
