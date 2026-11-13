import { test, expect } from 'playwright/test';
import { spawnSync } from 'node:child_process';
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

/**
 * #3244 — docker/institution.sh builds the institution folder from the
 * neutral defaults of the image and the files of the mounted folder. Only
 * theme.conf is required. The script runs here without a browser.
 */

const FRONTEND = resolve(import.meta.dirname, '../..');
const DEFAULT_DIR = join(FRONTEND, 'institution-default');

let mounted: string;
let out: string;

test.beforeEach(() => {
  mounted = mkdtempSync(join(tmpdir(), 'co2-mounted-'));
  out = mkdtempSync(join(tmpdir(), 'co2-out-'));
});

test.afterEach(() => {
  rmSync(mounted, { recursive: true, force: true });
  rmSync(out, { recursive: true, force: true });
});

const run = () =>
  spawnSync('sh', [join(FRONTEND, 'docker/institution.sh')], {
    env: {
      PATH: process.env.PATH,
      INSTITUTION_DIR: mounted,
      INSTITUTION_DEFAULT_DIR: DEFAULT_DIR,
      OUT_DIR: out,
    },
    encoding: 'utf8',
  });

const write = (file: string, content: string) => {
  mkdirSync(join(mounted, file, '..'), { recursive: true });
  writeFileSync(join(mounted, file), content);
};

test('a folder with only theme.conf gets every default asset', () => {
  write('theme.conf', 'accent: #0050a0\n');
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  expect(readFileSync(join(out, 'institution/logo.svg'))).toEqual(
    readFileSync(join(DEFAULT_DIR, 'logo.svg')),
  );
  expect(result.stdout).toContain(`logo.svg: from ${DEFAULT_DIR}`);
  const css = readFileSync(join(out, 'theme.css'), 'utf8');
  expect(css).toContain('--theme-accent: #0050a0;');
  expect(css).toContain('url("/institution/fonts/bold.woff2")');
});

test('a file of the mounted folder replaces its default', () => {
  write('theme.conf', 'accent: #0050a0\n');
  write('logo.svg', '<svg id="institution"/>');
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  expect(readFileSync(join(out, 'institution/logo.svg'), 'utf8')).toBe(
    '<svg id="institution"/>',
  );
  expect(result.stdout).toContain(`logo.svg: from ${mounted}`);
});

test('theme.conf points the fonts at a font server', () => {
  write(
    'theme.conf',
    'accent: #0050a0\nfont-regular: https://fonts.example.org/Regular.woff2\n',
  );
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  const css = readFileSync(join(out, 'theme.css'), 'utf8');
  expect(css).toContain('url("https://fonts.example.org/Regular.woff2")');
  expect(css).toContain('url("/institution/fonts/medium.woff2")');
});

test('a font value that is not a URL stops the startup', () => {
  write('theme.conf', 'accent: #0050a0\nfont-bold: javascript:alert(1)\n');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('"font-bold" must be an https:// URL');
});

test('a folder without theme.conf stops the startup', () => {
  write('logo.svg', '<svg/>');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('theme.conf. It sets the accent color.');
});

test('a file name the app does not know stops the startup', () => {
  write('theme.conf', 'accent: #0050a0\n');
  write('logo.png', 'png');
  write('.hidden', 'skipped, as the ..data entries of a ConfigMap');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain(`unknown files in ${mounted}: logo.png.`);
});

test('a font license next to the fonts is allowed, a font typo is not', () => {
  write('theme.conf', 'accent: #0050a0\n');
  write('fonts/OFL.txt', 'license');
  expect(run().status).toBe(0);
  write('fonts/Bold.woff2', 'font');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain(
    `unknown files in ${mounted}: fonts/Bold.woff2.`,
  );
});

test('a theme.conf with Windows line endings and blank lines is read', () => {
  write('theme.conf', '# theme\r\n\r\naccent: #0050a0\r\n');
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  expect(readFileSync(join(out, 'theme.css'), 'utf8')).toContain(
    '--theme-accent: #0050a0;',
  );
});
