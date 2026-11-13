// Institution values and assets outside the container (#3244).
//
// Why this exists: the container gets /injectEnv.js and /theme.css from
// docker/entrypoint.sh and docker/institution.sh at startup. `quasar dev`,
// `vite preview` and the component tests run the same two scripts here, so
// every run reads the institution the same way and the scripts have no
// second implementation in JavaScript.
//
// Two environment variables point at the institution:
//   INSTITUTION_ENV_FILE    the APP_* values (KEY=value lines)
//   INSTITUTION_ASSETS_DIR  the assets folder the container mounts
// Both are required: the values have no default, and the folder gives at
// least theme.conf. The other assets default to institution-default/.
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DOCKER_DIR = join(FRONTEND_DIR, 'docker');
const DEFAULT_DIR = join(FRONTEND_DIR, 'institution-default');

const requireEnv = (name) => {
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
 * preview`. Neither Quasar nor this script reads .env files by itself. Lines
 * are KEY=value, with optional quotes, and `#` starts a comment. A variable
 * already set in the shell wins, as with Vite.
 */
export const loadEnvLocal = () => {
  const envLocal = join(FRONTEND_DIR, '.env.local');
  if (!existsSync(envLocal)) return;
  for (const raw of readFileSync(envLocal, 'utf8').split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const m = line.match(/^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (!m) continue;
    let v = m[2].trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    if (process.env[m[1]] === undefined) process.env[m[1]] = v;
  }
};

/** KEY=value lines, `#` comments. Values are literal, like a compose env_file. */
export const readEnvFile = (file) => {
  const values = {};
  readFileSync(file, 'utf8')
    .split('\n')
    .forEach((raw, index) => {
      const line = raw.trim();
      if (!line || line.startsWith('#')) return;
      const match = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
      if (!match)
        throw new Error(`${file} line ${index + 1}: expected KEY=value`);
      values[match[1]] = match[2];
    });
  return values;
};

const run = (script, env) => {
  const result = spawnSync('sh', [join(DOCKER_DIR, script)], {
    env,
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error(`${script} failed:\n${result.stderr || result.stdout}`);
  }
};

/**
 * Write injectEnv.js, theme.css and the institution/ folder into outDir with
 * the container scripts. The shell environment wins over the env file, as in
 * the container.
 */
export const writeInstitutionFiles = (outDir) => {
  const values = readEnvFile(requireEnv('INSTITUTION_ENV_FILE'));
  const env = { ...values, ...process.env, OUT_DIR: outDir };
  run('entrypoint.sh', env);
  run('institution.sh', {
    ...env,
    INSTITUTION_DIR: requireEnv('INSTITUTION_ASSETS_DIR'),
    INSTITUTION_DEFAULT_DIR: DEFAULT_DIR,
  });
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
