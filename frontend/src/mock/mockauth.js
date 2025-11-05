import http from 'http';

const PORT = 8000;
const mockUser = {
  sciper: '123456',
  name: 'John Doe',
  email: 'john.doe@epfl.ch',
  roles: ['user'],
};

http
  .createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', 'http://localhost:9000');
    res.setHeader('Access-Control-Allow-Credentials', 'true');

    const cookies = {};
    if (req.headers.cookie) {
      req.headers.cookie.split(';').forEach((c) => {
        const [k, v] = c.trim().split('=');
        cookies[k] = v;
      });
    }

    if (req.url === '/api/v1/auth/login' && req.method === 'GET') {
      res.writeHead(302, {
        Location: 'http://localhost:9000/workspace-setup',
        'Set-Cookie': `auth_token=mock-${Date.now()}; HttpOnly; SameSite=Lax; Max-Age=86400; Path=/`,
      });
      res.end();
    } else if (req.url === '/api/v1/auth/me' && req.method === 'GET') {
      if (!cookies.auth_token)
        return res
          .writeHead(401)
          .end(JSON.stringify({ error: 'Not authenticated' }));
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(mockUser));
    } else if (req.url === '/api/v1/auth/logout' && req.method === 'POST') {
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'Set-Cookie': 'auth_token=; HttpOnly; Max-Age=0; Path=/',
      });
      res.end(JSON.stringify({ message: 'Logged out' }));
    } else {
      res.writeHead(404).end(JSON.stringify({ error: 'Not found' }));
    }
  })
  .listen(PORT, () => console.log(`Mock server: http://localhost:${PORT}`));
