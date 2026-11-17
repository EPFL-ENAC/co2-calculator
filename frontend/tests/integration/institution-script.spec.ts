import { test, expect } from 'playwright/test';
import { spawnSync } from 'node:child_process';
import {
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

/**
 * #3244 — docker/entrypoint.sh writes the values, builds the institution
 * folder from the neutral defaults of the image and the files of the mounted
 * folder, and writes the theme. A wrong value, file or theme line stops the
 * container. With a built page, it puts the values and the theme into the
 * page. The script runs here without a browser.
 */

const FRONTEND = resolve(import.meta.dirname, '../..');
const DEFAULT_DIR = join(FRONTEND, 'institution-default');
const ENV_FILE = resolve(FRONTEND, '../institutions/epfl/frontend.env.example');

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

// `env` stands for the pod environment, on top of the tracked values.
const run = (env: Record<string, string> = {}) =>
  spawnSync('sh', [join(FRONTEND, 'docker/entrypoint.sh')], {
    env: {
      PATH: process.env.PATH,
      INSTITUTION_ENV_FILE: ENV_FILE,
      INSTITUTION_DIR: mounted,
      INSTITUTION_DEFAULT_DIR: DEFAULT_DIR,
      OUT_DIR: out,
      // No built page, as for the dev server: the values and the theme
      // stay files. The page tests below set one.
      INDEX_HTML: '',
      ...env,
    },
    encoding: 'utf8',
  });

const write = (file: string, content: string) => {
  mkdirSync(join(mounted, file, '..'), { recursive: true });
  writeFileSync(join(mounted, file), content);
};

const theme = (content: string) => write('theme.conf', content);

// What the browser reads from a script that sets the values.
const evaluate = (script: string): Record<string, string> => {
  const scope: { injectedEnvVariable?: Record<string, string> } = {};
  new Function('window', script)(scope);
  return scope.injectedEnvVariable ?? {};
};

const injected = () =>
  evaluate(readFileSync(join(out, 'injectEnv.js'), 'utf8'));

// The two tags as the build writes them: minified, attributes not quoted.
const BUILT_PAGE =
  '<!doctype html><html><head><title>t</title>' +
  '<link rel=stylesheet href=/theme.css><script src=/injectEnv.js defer></script>' +
  '<script type="module" src="/assets/index.js"></script></head>' +
  '<body><div id=q-app></div></body></html>\n';

// The read-only page of the image, outside OUT_DIR. The script skips a
// name that starts with "." in the mounted folder.
const builtPage = (content = BUILT_PAGE) => {
  const file = join(mounted, '.built-index.html');
  writeFileSync(file, content);
  return file;
};

const page = () => readFileSync(join(out, 'index.html'), 'utf8');

// What an HTML parser takes as the content of the values element: up to the
// first end tag.
const inlineValues = () => {
  const open = '<script id="institution-values">';
  const html = page();
  const start = html.indexOf(open) + open.length;
  return evaluate(html.slice(start, html.indexOf('</script', start)));
};

test('a folder with only theme.conf gets every default asset', () => {
  theme('accent: #0050a0\n');
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
  theme('accent: #0050a0\n');
  write('logo.svg', '<svg id="institution"/>');
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  expect(readFileSync(join(out, 'institution/logo.svg'), 'utf8')).toBe(
    '<svg id="institution"/>',
  );
  expect(result.stdout).toContain(`logo.svg: from ${mounted}`);
});

test('theme.conf points the fonts at a font server', () => {
  theme(
    'accent: #0050a0\nfont-regular: https://fonts.example.org/Regular.woff2\n',
  );
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  const css = readFileSync(join(out, 'theme.css'), 'utf8');
  expect(css).toContain('url("https://fonts.example.org/Regular.woff2")');
  expect(css).toContain('url("/institution/fonts/medium.woff2")');
});

// Each value is pasted into CSS, so only one shape per kind passes.
for (const [line, message] of [
  ['font-bold: javascript:alert(1)', '"font-bold" must be an https:// URL'],
  ['font-bold: //fonts.example.org/b.woff2', '"font-bold" must be an https://'],
  ['font-bold: https://f.example.org/a").woff2', '"font-bold" must be an'],
  ['accent-hover: red', '"accent-hover" must be a hex color'],
  ['accent-hover: #12345', '"accent-hover" must be a hex color'],
  ['accent-hover: url(https://x.example.org)', '"accent-hover" must be a hex'],
  ['radius: 1px; } body { color: red', '"radius" must be a length'],
  // In the page the theme is a style element: nothing may close it.
  ['accent-hover: #fff</style>', '"accent-hover" must be a hex color'],
  ['font-bold: /fonts/b.woff2</style>', '"font-bold" must be an https://'],
  ['shadow: 1px', 'unknown name "shadow"'],
]) {
  test(`the theme line "${line}" stops the startup`, () => {
    theme(`accent: #0050a0\n${line}\n`);
    const result = run();
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(message);
  });
}

test('a folder without theme.conf stops the startup', () => {
  write('logo.svg', '<svg/>');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('theme.conf. It sets the accent color.');
});

test('a file name the app does not know stops the startup', () => {
  theme('accent: #0050a0\n');
  write('logo.png', 'png');
  write('.hidden', 'skipped, as the ..data entries of a ConfigMap');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain(`unknown files in ${mounted}: logo.png.`);
});

test('a font license next to the fonts is allowed, a font typo is not', () => {
  theme('accent: #0050a0\n');
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
  theme('# theme\r\n\r\naccent: #0050a0\r\n');
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  expect(readFileSync(join(out, 'theme.css'), 'utf8')).toContain(
    '--theme-accent: #0050a0;',
  );
});

test('the values reach the browser, and the environment wins over the file', () => {
  theme('accent: #0050a0\n');
  const result = run({ APP_INSTITUTION_NAME: 'A "quoted" \\ name' });
  expect(result.status, result.stderr).toBe(0);
  const values = injected();
  expect(values.APP_INSTITUTION_NAME).toBe('A "quoted" \\ name');
  // From the file, with its apostrophe as it is.
  expect(values.APP_INSTITUTION_NAME_FR_DE).toMatch(/^de l'/);
});

// A wrong value stops the container, so a rollout keeps the old pods.
for (const [env, message] of [
  [{ APP_CONTACT_EMAIL: '' }, 'APP_CONTACT_EMAIL is required and empty'],
  [{ APP_USER_DOC_URL: 'https://doc.example.org' }, 'must end with /'],
  [{ APP_MATOMO_SITE_ID: '3' }, 'APP_MATOMO_URL is required'],
  [{ APP_DEMO_MODE: 'true' }, 'APP_PRODUCTION_URL is required'],
  [{ APP_API_TOKEN: 'abc' }, 'APP_API_TOKEN: every APP_* value is public'],
] as const) {
  test(`${Object.keys(env)[0]} stops the startup: ${message}`, () => {
    theme('accent: #0050a0\n');
    const result = run(env);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(message);
  });
}

test('an env file line that is not APP_<NAME>=value stops the startup', () => {
  theme('accent: #0050a0\n');
  const file = join(out, 'bad.env');
  writeFileSync(file, 'APP_INSTITUTION_NAME\n');
  const result = run({ INSTITUTION_ENV_FILE: file });
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('line 1: expected APP_<NAME>=value');
});

test('with a built page, the values and the theme go into the page', () => {
  theme('accent: #0050a0\n');
  const result = run({ INDEX_HTML: builtPage() });
  expect(result.status, result.stderr).toBe(0);
  const html = page();
  expect(html).toContain('<style id="institution-theme">:root {');
  expect(html).toContain('--theme-accent: #0050a0;');
  expect(inlineValues().APP_INSTITUTION_NAME_FR_DE).toMatch(/^de l'/);
  // The two requests are gone: no tag loads them, and no file is left.
  expect(html).not.toContain('/theme.css');
  expect(html).not.toContain('/injectEnv.js');
  expect(existsSync(join(out, 'theme.css'))).toBe(false);
  expect(existsSync(join(out, 'injectEnv.js'))).toBe(false);
  // The rest of the page is as built.
  expect(html.startsWith('<!doctype html><html><head><title>t</title>')).toBe(
    true,
  );
  expect(
    html.endsWith(
      '</script><script type="module" src="/assets/index.js"></script></head>' +
        '<body><div id=q-app></div></body></html>\n',
    ),
  ).toBe(true);
});

test('a value cannot close the script element of the page', () => {
  theme('accent: #0050a0\n');
  const value = 'a</script><script>alert(1)</script><!-- & \\ "q"';
  const result = run({ INDEX_HTML: builtPage(), APP_INSTITUTION_NAME: value });
  expect(result.status, result.stderr).toBe(0);
  expect(inlineValues().APP_INSTITUTION_NAME).toBe(value);
  // The values element and the module script of the build, no third one.
  expect(page().match(/<script/g)).toHaveLength(2);
  expect(page()).not.toContain('<!--');
});

test('a second run on its own page replaces the values and the theme', () => {
  theme('accent: #0050a0\n');
  expect(run({ INDEX_HTML: builtPage() }).status).toBe(0);
  const first = page();
  // `vite preview` starts again on the page of the last run.
  const ownPage = join(out, 'index.html');
  theme('accent: #00ff00\n');
  const again = run({ INDEX_HTML: ownPage, APP_INSTITUTION_NAME: 'Other' });
  expect(again.status, again.stderr).toBe(0);
  expect(page()).toContain('--theme-accent: #00ff00;');
  expect(page()).not.toContain('#0050a0');
  expect(inlineValues().APP_INSTITUTION_NAME).toBe('Other');
  theme('accent: #0050a0\n');
  expect(run({ INDEX_HTML: ownPage }).status).toBe(0);
  expect(page()).toBe(first);
});

test('a page without the two tags stops the startup', () => {
  theme('accent: #0050a0\n');
  const result = run({
    INDEX_HTML: builtPage('<html><head></head><body></body></html>\n'),
  });
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('no tag loads /theme.css');
  expect(existsSync(join(out, 'index.html'))).toBe(false);
});

test('a built page that does not exist stops the startup', () => {
  theme('accent: #0050a0\n');
  const result = run({ INDEX_HTML: join(out, 'missing.html') });
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('missing or empty');
});
