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
 * container. The script runs here without a browser.
 */

const FRONTEND = resolve(import.meta.dirname, '../..');
const DEFAULT_DIR = join(FRONTEND, 'institution-default');
const EXAMPLE_VALUES = readFileSync(
  join(FRONTEND, 'institution-example/values.env'),
  'utf8',
);

let mounted: string;
let out: string;

test.beforeEach(() => {
  mounted = mkdtempSync(join(tmpdir(), 'co2-mounted-'));
  out = mkdtempSync(join(tmpdir(), 'co2-out-'));
  // The mounted folder gives the values, as a deployment folder does.
  writeFileSync(join(mounted, 'values.env'), EXAMPLE_VALUES);
});

test.afterEach(() => {
  rmSync(mounted, { recursive: true, force: true });
  rmSync(out, { recursive: true, force: true });
});

// `env` stands for the pod environment, on top of values.env.
const run = (env: Record<string, string> = {}) =>
  spawnSync('sh', [join(FRONTEND, 'docker/entrypoint.sh')], {
    env: {
      PATH: process.env.PATH,
      INSTITUTION_DIR: mounted,
      INSTITUTION_DEFAULT_DIR: DEFAULT_DIR,
      OUT_DIR: out,
      ...env,
    },
    encoding: 'utf8',
  });

const write = (file: string, content: string) => {
  mkdirSync(join(mounted, file, '..'), { recursive: true });
  writeFileSync(join(mounted, file), content);
};

const theme = (content: string) => write('theme.conf', content);

// What the browser reads from injectEnv.js.
const injected = (): Record<string, string> => {
  const scope: { injectedEnvVariable?: Record<string, string> } = {};
  new Function('window', readFileSync(join(out, 'injectEnv.js'), 'utf8'))(
    scope,
  );
  return scope.injectedEnvVariable ?? {};
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
  expect(css).toContain('url("/institution/font-bold.woff2")');
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
  expect(css).toContain('url("/institution/font-medium.woff2")');
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
  write('font-license.txt', 'license');
  expect(run().status).toBe(0);
  expect(existsSync(join(out, 'institution/font-license.txt'))).toBe(false);
  write('font-Bold.woff2', 'font');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain(
    `unknown files in ${mounted}: font-Bold.woff2.`,
  );
});

test('a subfolder in the mounted folder stops the startup', () => {
  theme('accent: #0050a0\n');
  write('fonts/font-regular.woff2', 'font');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain(
    `subfolders in ${mounted}: fonts. The folder is flat`,
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
  [{ APP_PLANNER_MAX_YEAR: '' }, 'APP_PLANNER_MAX_YEAR is required and empty'],
  [{ APP_PLANNER_MIN_YEAR: '20x6' }, 'APP_PLANNER_MIN_YEAR must be a year'],
  [{ APP_PLANNER_MIN_YEAR: '2051' }, 'must not be after APP_PLANNER_MAX_YEAR'],
] as const) {
  test(`${Object.keys(env)[0]} stops the startup: ${message}`, () => {
    theme('accent: #0050a0\n');
    const result = run(env);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(message);
  });
}

for (const name of ['APP_ENVIRONMENT', 'APP_DEMO_MODE']) {
  test(`${name} in values.env stops the startup`, () => {
    theme('accent: #0050a0\n');
    write('values.env', `${EXAMPLE_VALUES}${name}=x\n`);
    const result = run();
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(
      `${name} belongs to the cluster, set it in the environment`,
    );
  });
}

test('a values.env line that is not APP_<NAME>=value stops the startup', () => {
  theme('accent: #0050a0\n');
  write('values.env', 'APP_INSTITUTION_NAME\n');
  const result = run();
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('line 1: expected APP_<NAME>=value');
});

// A deployment can give every value through the environment.
test('a line break in a value of the environment stops the startup', () => {
  theme('accent: #0050a0\n');
  // printenv would give "APP_INJECTED=two" as a second variable.
  const result = run({ APP_ROLES_DOC_URL: 'one\nAPP_INJECTED=two' });
  expect(result.status).toBe(1);
  expect(result.stderr).toContain(
    'APP_ROLES_DOC_URL: a value cannot hold a line break',
  );
  expect(result.stderr).not.toContain('APP_INJECTED');
});

test('a name with another character in the environment stops the startup', () => {
  theme('accent: #0050a0\n');
  const result = run({ 'APP_K"Y': '1' });
  expect(result.status).toBe(1);
  expect(result.stderr).toContain('a name is APP_ and then capital letters');
});

test('the log names a value that the environment replaces', () => {
  theme('accent: #0050a0\n');
  const result = run({ APP_CONTACT_EMAIL: '', APP_INSTITUTION_NAME: 'Other' });
  expect(result.stderr).toContain(
    'APP_INSTITUTION_NAME: the environment replaces values.env',
  );
  // An empty variable replaces the value too, and the value is required.
  expect(result.stderr).toContain(
    'APP_CONTACT_EMAIL: the environment replaces values.env',
  );
  expect(result.status).toBe(1);
});

test('a folder without values.env starts on the environment alone', () => {
  theme('accent: #0050a0\n');
  rmSync(join(mounted, 'values.env'));
  const env = Object.fromEntries(
    EXAMPLE_VALUES.split('\n')
      .filter((line) => line.startsWith('APP_'))
      .map((line) => [
        line.slice(0, line.indexOf('=')),
        line.slice(line.indexOf('=') + 1),
      ]),
  );
  const result = run(env);
  expect(result.status, result.stderr).toBe(0);
  expect(injected().APP_INSTITUTION_NAME).toBe('Example University');
});

test('values.env is never served in the institution folder', () => {
  theme('accent: #0050a0\n');
  const result = run();
  expect(result.status, result.stderr).toBe(0);
  expect(existsSync(join(out, 'institution/values.env'))).toBe(false);
});

test('an environment variable wins over values.env', () => {
  theme('accent: #0050a0\n');
  const result = run({ APP_CONTACT_EMAIL: 'other@example.org' });
  expect(result.status, result.stderr).toBe(0);
  expect(injected().APP_CONTACT_EMAIL).toBe('other@example.org');
});
