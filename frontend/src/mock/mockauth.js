import http from 'http';

const PORT = 8000;
const mockUser = {
  sciper: '123456',
  name: 'John Doe',
  email: 'john.doe@epfl.ch',
  roles: ['user'],
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
    if (
      k === '__proto__' ||
      k === 'constructor' ||
      k === 'prototype'
    ) {
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

    if (req.url === '/api/v1/auth/login' && req.method === 'GET') {
      res.writeHead(302, {
        Location: 'http://localhost:9000/workspace-setup',
        'Set-Cookie': `auth_token=mock-${Date.now()}; HttpOnly; SameSite=Lax; Max-Age=86400; Path=/`,
      });
      res.end();
    } else if (req.url === '/api/v1/auth/me' && req.method === 'GET') {
      if (!cookies.auth_token) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not authenticated' }));
        return;
      }

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(mockUser));
    } else if (req.url === '/api/v1/auth/logout' && req.method === 'POST') {
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
