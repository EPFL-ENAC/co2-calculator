// Serves the institution assets folder at /institution/ under `quasar dev`
// (#500). In a container nginx serves the mounted folder; the bundle ships
// no logo, icon or font of its own, so the dev server needs the same URL.
import fs from 'node:fs';
import path from 'node:path';

const CONTENT_TYPES = {
  '.css': 'text/css',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

export function institutionAssetsPlugin(assetsDir) {
  return {
    name: 'institution-assets',
    apply: 'serve',
    configureServer(server) {
      if (!assetsDir) {
        throw new Error(
          'INSTITUTION_ASSETS_DIR is not set. Set it in frontend/.env.local ' +
            '(see frontend/.env.example).',
        );
      }
      const root = path.resolve(assetsDir);
      server.middlewares.use('/institution', (req, res, next) => {
        const file = path.join(root, decodeURIComponent(req.url.split('?')[0]));
        if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) {
          next();
          return;
        }
        const type = CONTENT_TYPES[path.extname(file)];
        if (type) res.setHeader('Content-Type', type);
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}
