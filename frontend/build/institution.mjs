// Institution values and assets outside the container (#3244).
//
// Why this exists: in the container, docker/entrypoint.sh writes
// injectEnv.js, theme.css and the institution/ folder at startup, and nginx
// serves them. `quasar dev`, `vite preview`, the component tests and
// Storybook run that same script here, into a folder that Vite serves as its
// public folder. This file holds no parser, no check and no file server: it
// only starts the script.
//
// INSTITUTION_DIR points at the institution folder, the one the container
// mounts: values.env, theme.conf and the assets. A relative path starts at
// frontend/. Without it, the neutral example folder institution-example/ runs.
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const institutionDir = () => {
  const value = process.env.INSTITUTION_DIR ?? 'institution-example';
  const path = resolve(FRONTEND_DIR, value);
  if (!existsSync(path)) {
    throw new Error(
      `INSTITUTION_DIR=${value} does not exist (${path}). See frontend/.env.example.`,
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
      INSTITUTION_DIR: institutionDir(),
      INSTITUTION_DEFAULT_DIR: join(FRONTEND_DIR, 'institution-default'),
    },
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error(`docker/entrypoint.sh failed:\n${result.stderr}`);
  }
};

/**
 * Vite plugin for the dev server and Storybook. A dev server serves the
 * script output as its public folder, so Vite does what nginx does in the
 * container, and writes it again when a file of the institution changes. A
 * build (Storybook) writes the files next to its output. The app build never
 * uses this plugin: there the container writes them.
 */
export const institutionPlugin = () => {
  let outDir;
  return {
    name: 'institution-assets',
    config(_config, { command }) {
      if (command !== 'serve') return;
      outDir = mkdtempSync(join(tmpdir(), 'co2-institution-'));
      // Fail at startup, not on the first request, when the setup is wrong.
      writeInstitutionFiles(outDir);
      return { publicDir: outDir };
    },
    configureServer(server) {
      const source = institutionDir();
      server.watcher.add(source);
      // 'all': a file that is added or removed changes the folder too.
      server.watcher.on('all', (_event, file) => {
        if (!file.startsWith(source)) return;
        try {
          writeInstitutionFiles(outDir);
          server.ws.send({ type: 'full-reload' });
        } catch (e) {
          // Keep the dev server and the last good files: the edit is wrong.
          server.config.logger.error(
            e instanceof Error ? e.message : String(e),
          );
        }
      });
    },
    writeBundle(options) {
      writeInstitutionFiles(options.dir);
    },
  };
};
