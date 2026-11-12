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
// Both are required. There is no default institution.
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DOCKER_DIR = join(FRONTEND_DIR, 'docker');

const requireEnv = (name) => {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `${name} is not set. Point it at an institution, see frontend/.env.example.`,
    );
  }
  return resolve(FRONTEND_DIR, value);
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
 * Write injectEnv.js and theme.css into outDir with the container scripts.
 * The shell environment wins over the env file, as in the container.
 */
export const writeInstitutionFiles = (outDir) => {
  const values = readEnvFile(requireEnv('INSTITUTION_ENV_FILE'));
  const env = { ...values, ...process.env, OUT_DIR: outDir };
  run('entrypoint.sh', env);
  run('institution.sh', {
    ...env,
    INSTITUTION_DIR: requireEnv('INSTITUTION_ASSETS_DIR'),
  });
};

/** Copy the assets folder to outDir/institution, where nginx serves it. */
export const copyInstitutionAssets = (outDir) => {
  const target = join(outDir, 'institution');
  rmSync(target, { recursive: true, force: true });
  cpSync(requireEnv('INSTITUTION_ASSETS_DIR'), target, { recursive: true });
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
 * server generates the files on each request, so an edit shows on reload. A
 * build (component tests, Storybook) writes them next to its output. The app
 * build never uses it: there the container writes them.
 */
export const institutionPlugin = () => ({
  name: 'institution-assets',
  writeBundle(options) {
    writeInstitutionFiles(options.dir);
    copyInstitutionAssets(options.dir);
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
      const root = requireEnv('INSTITUTION_ASSETS_DIR');
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
