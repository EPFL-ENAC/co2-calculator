// Fails the type check when a Quasar stylesheet in use is not imported.
//
// src/css/_quasar-base.scss imports only the Quasar stylesheets the app
// needs, to keep the render-blocking entry CSS small. A component used
// without its stylesheet renders unstyled and nothing errors at runtime,
// so this check is the only place the gap shows.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';

const FRONTEND = new URL('../', import.meta.url).pathname;
const QUASAR = join(FRONTEND, 'node_modules/quasar/src');
const PARTIAL = 'src/css/_quasar-base.scss';

// Component folders without a stylesheet of their own: where Quasar keeps
// their rules, or null when they have none.
const STYLED_ELSEWHERE = {
  drawer: 'components/layout/QLayout.sass',
  footer: 'components/layout/QLayout.sass',
  header: 'components/layout/QLayout.sass',
  page: 'components/layout/QLayout.sass',
  'page-scroller': 'components/layout/QLayout.sass',
  'page-sticky': 'components/layout/QLayout.sass',
  'markup-table': 'components/table/QTable.sass',
  range: 'components/slider/QSlider.sass',
  'no-ssr': null,
  'popup-proxy': null,
  'resize-observer': null,
  'scroll-observer': null,
  'slide-transition': null,
};

const read = (file) => readFileSync(file, 'utf8');
const imports = (source, pattern) =>
  [...source.matchAll(pattern)].map((match) => match[1]);
const walk = (dir, pattern) =>
  readdirSync(dir, { recursive: true })
    .filter((file) => pattern.test(file))
    .map((file) => join(dir, file));

// Every stylesheet Quasar ships, as paths relative to quasar/src.
const shipped = new Set(
  imports(read(join(QUASAR, 'css/index.sass')), /^@import '(.+)'$/gm).map(
    (path) => relative(QUASAR, join(QUASAR, 'css', path)),
  ),
);
const imported = new Set(
  imports(read(join(FRONTEND, PARTIAL)), /@import 'quasar\/src\/(.+)';/g),
);

// What the app uses: components by tag or by name, directives, plugins.
// Storybook loads the same app.scss, so its stories count as well.
const app = ['src', 'storybook/stories']
  .flatMap((dir) => walk(join(FRONTEND, dir), /\.(vue|ts)$/))
  .map(read)
  .join('\n');
const config = read(join(FRONTEND, 'quasar.config.js'));
const pascal = (kebab) =>
  kebab.replace(/(^|-)([a-z])/g, (_, _dash, letter) => letter.toUpperCase());
const names = new Set([
  ...imports(app, /<(q-[a-z-]+)/g).map(pascal),
  ...imports(app, /\b(Q[A-Z][A-Za-z]+)\b/g),
]);
const roots = [
  ...walk(join(QUASAR, 'components'), /^[a-z-]+\/Q[A-Za-z]+\.js$/).filter(
    (file) => names.has(file.slice(file.lastIndexOf('/') + 1, -3)),
  ),
  ...readdirSync(join(QUASAR, 'directives'))
    .filter((dir) => app.includes(`v-${dir}`))
    .map((dir) => join(QUASAR, 'directives', dir, `${pascal(dir)}.js`)),
  ...readdirSync(join(QUASAR, 'plugins'))
    .filter((dir) => config.includes(`'${pascal(dir)}'`))
    .map((dir) => join(QUASAR, 'plugins', dir, `${pascal(dir)}.js`)),
];

// Quasar components use each other (a select opens a menu): follow the
// imports so that the stylesheets of the inner components count too.
const visited = new Set();
const queue = [...roots];
while (queue.length > 0) {
  const file = queue.pop();
  if (visited.has(file)) continue;
  if (!existsSync(file)) throw new Error(`${file}: no such Quasar file`);
  visited.add(file);
  for (const path of imports(read(file), /from '(\.[^']+\.js)'/g)) {
    queue.push(join(dirname(file), path));
  }
}

const needed = new Set();
for (const file of visited) {
  const own = relative(QUASAR, file).replace(/\.js$/, '.sass');
  const dir = dirname(own);
  // A helper next to a component (use-spinner.js) has no rules of its own.
  if (!shipped.has(own) && !/\/Q[A-Za-z]+\.sass$/.test(own)) continue;
  // A folder shares one stylesheet (QTabs.sass styles QTab) unless the
  // component has its own (each spinner).
  let sheets = [...shipped].filter((sass) => dirname(sass) === dir);
  if (shipped.has(own)) sheets = [own];
  if (sheets.length === 0) {
    const folder = dir.slice('components/'.length);
    if (!(folder in STYLED_ELSEWHERE)) {
      throw new Error(
        `Quasar component folder "${folder}" has no stylesheet: ` +
          'say where its rules are in STYLED_ELSEWHERE (scripts/check-quasar-css.mjs)',
      );
    }
    sheets = [STYLED_ELSEWHERE[folder]].filter(Boolean);
  }
  for (const sheet of sheets) needed.add(sheet);
}

// Quasar's helpers and core rules (colors, flex, ...) are not optional.
const core = [...shipped].filter((sass) => sass.startsWith('css/'));
for (const sass of core) needed.add(sass);

const missing = [...needed].filter((sass) => !imported.has(sass)).sort();
if (missing.length > 0) {
  for (const sass of missing) {
    console.error(
      `${PARTIAL}: the app uses it, add @import 'quasar/src/${sass}';`,
    );
  }
  process.exit(1);
}
console.log(
  `quasar css: ${needed.size} stylesheets in use, all imported ` +
    `(${shipped.size} shipped by Quasar)`,
);
