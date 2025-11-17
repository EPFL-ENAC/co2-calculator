import http from 'http';

import console from 'console';

const PORT = 8000;
const mockUser = {
  id: 'aea',
  sciper: 414,
  email: 'email@epfl.ch',
  roles: [
    { role: 'co2.user.principal', on: { unit: '67890' } },
    { role: 'co2.user.secondary', on: { unit: '12344' } },
    { role: 'co2.user.std', on: { unit: '12345' } },
  ],
};

// safer: no inherited prototype
function parseCookies(header) {
  const cookies = Object.create(null);
  if (!header) return cookies;

  header.split(';').forEach((c) => {
    const [rawK, rawV] = c.trim().split('=');
    const k = String(rawK || '');
    const v = String(rawV || '');

    // prevent prototype pollution
    if (k === '__proto__' || k === 'constructor' || k === 'prototype') {
      return;
    }
    cookies[k] = v;
  });

  return cookies;
}

http
  .createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', 'http://localhost:9000');
    res.setHeader('Access-Control-Allow-Credentials', 'true');

    const cookies = parseCookies(req.headers.cookie);

    if (req.url === '/v1/auth/login' && req.method === 'GET') {
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'Set-Cookie': `auth_token=mock-${Date.now()}; HttpOnly; SameSite=Lax; Max-Age=86400; Path=/`,
      });
      res.end(JSON.stringify(mockUser));
    } else if (req.url === '/v1/auth/me' && req.method === 'GET') {
      if (!cookies.auth_token) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not authenticated' }));
        return;
      }

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(mockUser));
    } else if (req.url === '/v1/auth/logout' && req.method === 'POST') {
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'Set-Cookie': 'auth_token=; HttpOnly; Max-Age=0; Path=/',
      });
      res.end(JSON.stringify({ message: 'Logged out' }));
    } else {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Not found' }));
    }
  })
  .listen(PORT, () => console.log(`Mock server: http://localhost:${PORT}`));
