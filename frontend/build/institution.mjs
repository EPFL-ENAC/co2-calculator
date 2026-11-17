// Institution values and assets outside the container (#3244).
//
// Why this exists: in the container, docker/entrypoint.sh writes
// injectEnv.js, theme.css and the institution/ folder at startup, and nginx
// serves them. `quasar dev`, `vite preview`, the component tests and
// Storybook run that same script here. This file holds no parser and no
// check: it starts the script and serves its output.
//
// Two environment variables point at the institution:
//   INSTITUTION_ENV_FILE    the APP_* values (APP_<NAME>=value lines)
//   INSTITUTION_ASSETS_DIR  the assets folder the container mounts
// Both are required: the values have no default, and the folder gives at
// least theme.conf. The other assets default to institution-default/.
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const requirePath = (name) => {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `${name} is not set. Point it at an institution, see frontend/.env.example.`,
    );
  }
  const path = resolve(FRONTEND_DIR, value);
  if (!existsSync(path)) {
    throw new Error(
      `${name}=${value} does not exist (${path}). The root \`make install\` ` +
        'copies institutions/epfl/frontend.env.example to frontend.env.',
    );
  }
  return path;
};

/**
 * Load frontend/.env.local into process.env, for `quasar dev` and `npm run
 * preview`: neither reads .env files by itself. Node parses the file, and a
 * variable already set in the shell wins.
 */
export const loadEnvLocal = () => {
  const envLocal = join(FRONTEND_DIR, '.env.local');
  if (existsSync(envLocal)) process.loadEnvFile(envLocal);
};

/**
 * Write injectEnv.js, theme.css and the institution/ folder into outDir with
 * the container script. A wrong value or file throws with the script's error.
 */
export const writeInstitutionFiles = (outDir) => {
  const result = spawnSync('sh', [join(FRONTEND_DIR, 'docker/entrypoint.sh')], {
    env: {
      ...process.env,
      OUT_DIR: outDir,
      INSTITUTION_ENV_FILE: requirePath('INSTITUTION_ENV_FILE'),
      INSTITUTION_DIR: requirePath('INSTITUTION_ASSETS_DIR'),
      INSTITUTION_DEFAULT_DIR: join(FRONTEND_DIR, 'institution-default'),
    },
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error(`docker/entrypoint.sh failed:\n${result.stderr}`);
  }
};

const CONTENT_TYPES = {
  '.css': 'text/css',
  '.ico': 'image/x-icon',
  '.js': 'application/javascript',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
};

const send = (res, file) => {
  res.setHeader(
    'Content-Type',
    CONTENT_TYPES[extname(file)] || 'application/octet-stream',
  );
  res.setHeader('Cache-Control', 'no-cache');
  res.end(readFileSync(file));
};

/**
 * Vite plugin for the dev server, the component tests and Storybook: serves
 * /injectEnv.js, /theme.css and /institution/* the way nginx does. A dev
 * server generates the files on each request of /injectEnv.js or
 * /theme.css, which a reload makes first, so an edit shows on reload. A
 * build (component tests, Storybook) writes them next to its output. The app
 * build never uses it: there the container writes them.
 */
export const institutionPlugin = () => ({
  name: 'institution-assets',
  writeBundle(options) {
    writeInstitutionFiles(options.dir);
  },
  configureServer(server) {
    const outDir = mkdtempSync(join(tmpdir(), 'co2-institution-'));
    // Fail at startup, not on the first request, when the setup is wrong.
    writeInstitutionFiles(outDir);
    server.middlewares.use((req, res, next) => {
      const path = (req.url || '').split('?')[0];
      if (path === '/injectEnv.js' || path === '/theme.css') {
        writeInstitutionFiles(outDir);
        send(res, join(outDir, path.slice(1)));
        return;
      }
      if (!path.startsWith('/institution/')) {
        next();
        return;
      }
      const root = join(outDir, 'institution');
      const relative = decodeURIComponent(path.slice('/institution/'.length));
      const file = normalize(join(root, relative));
      // A request path never leaves the assets folder.
      if (!file.startsWith(root + sep) || !existsSync(file)) {
        res.statusCode = 404;
        res.end();
        return;
      }
      send(res, file);
    });
  },
});
