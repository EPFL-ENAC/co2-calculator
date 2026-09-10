// Fails the build on icons still written as Material *ligature strings*.
//
// Since #1603 the webfonts are gone, so `icon="chevron_left"` no longer draws
// a glyph -- Quasar emits <i class="material-icons">chevron_left</i> and the
// browser renders the literal word. Nothing errors: not TypeScript (the prop
// is `string`), not the build, not a unit test. It only shows up by looking at
// the page, which is how five of these survived #1603 itself.
//
// Icons must be imported SVG constants instead:
//   import { matChevronLeft } from '@quasar/extras/material-icons';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const SRC = new URL('../src/', import.meta.url).pathname;

// Export names ("matChevronLeft") -> ligature names ("chevron_left"), which is
// what the webfont wanted and therefore what the stale call sites still say.
const ligatures = new Set(
  ['material-icons', 'material-icons-outlined'].flatMap((pkg) =>
    JSON.parse(
      readFileSync(`node_modules/@quasar/extras/${pkg}/icons.json`, 'utf8'),
    ).map((name) =>
      name
        .replace(/^(mat|outlined)/, '')
        .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
        .toLowerCase(),
    ),
  ),
);

const RULES = [
  // <q-btn button-icon="file_upload">  -- static attribute, so not a binding
  [/\b[a-z-]*icon="([a-z][a-z0-9_]*)"/g, (m) => ligatures.has(strip(m[1]))],
  // { buttonIcon: 'add' }  -- prop default or config object
  [
    /\b[a-zA-Z]*[iI]con:\s*'([a-z][a-z0-9_]*)'/g,
    (m) => ligatures.has(strip(m[1])),
  ],
  // cond ? 'o_comment' : 'o_add_comment'  -- the shape that hid in computeds.
  // Both sides must be icons AND one must carry an `o_` prefix or an
  // underscore, or this matches every `? 'edit' : 'add'` mode flag in the
  // codebase: plenty of single-word ligature names are also ordinary enums.
  [
    /\?\s*'([a-z][a-z0-9_]*)'\s*:\s*'([a-z][a-z0-9_]*)'/g,
    (m) =>
      ligatures.has(strip(m[1])) &&
      ligatures.has(strip(m[2])) &&
      /^o_|_/.test(m[1] + m[2]),
  ],
];

// `o_` is Quasar's outlined-set prefix; it is not part of the ligature itself.
const strip = (name) => name.replace(/^o_/, '');

function* walk(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else if (/\.(vue|ts)$/.test(e.name)) yield p;
  }
}

const found = [];
for (const file of walk(SRC)) {
  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, i) => {
    for (const [re, isIcon] of RULES) {
      for (const m of line.matchAll(re)) {
        if (isIcon(m))
          found.push(`src/${file.slice(SRC.length)}:${i + 1}  ${m[0].trim()}`);
      }
    }
  });
}

if (found.length) {
  console.error(
    `\n${found.length} icon(s) written as a webfont ligature string.\n` +
      `The webfonts were dropped in #1603, so these render as literal text.\n` +
      `Import the SVG constant instead (e.g. matChevronLeft):\n`,
  );
  for (const hit of found) console.error(`  ${hit}`);
  process.exit(1);
}
console.log('No webfont ligature icons found.');
