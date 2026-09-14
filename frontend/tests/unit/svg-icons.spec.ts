/**
 * Guards the "no icon webfont" invariant.
 *
 * Icons ship as inline SVG imported per component from `@quasar/extras`, so
 * only the icons actually used are bundled. Two things silently undo that:
 * putting `material-icons` back into `extras` (the fonts return to the LCP
 * critical path), or writing a ligature name (`icon="close"`) instead of a
 * bound SVG import — which, with no font loaded, renders nothing at all.
 * Both are compile-clean, so the type-checker cannot catch them.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/experimental-ct-vue';
import svgMaterialIcons from 'quasar/icon-set/svg-material-icons.js';

import ChartContainer from '../../src/components/molecules/ChartContainer.vue';

const FRONTEND = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);
const SRC = path.join(FRONTEND, 'src');

// Props that carry a Quasar icon. Unbound (`icon="x"`) means a ligature name.
const ICON_ATTRS = [
  'icon',
  'icon-right',
  'icon-left',
  'dropdown-icon',
  'expand-icon',
  'clear-icon',
  'toggle-icon',
  'append-icon',
  'prepend-icon',
  'checked-icon',
  'unchecked-icon',
  'indeterminate-icon',
];

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) sourceFiles(full, out);
    else if (['.vue', '.ts'].includes(path.extname(full))) out.push(full);
  }
  return out;
}

// Strips whole-line runs of an open HTML comment block. Commented-out markup
// renders nothing, so it is not a call site; un-commenting it makes the name
// live again and this guard fires on it.
function outsideComment(line: string, state: { open: boolean }): string {
  let rest = line;
  if (state.open) {
    const close = rest.indexOf('-->');
    if (close < 0) return '';
    rest = rest.slice(close + 3);
    state.open = false;
  }
  const start = rest.lastIndexOf('<!--');
  if (start < 0 || rest.includes('-->', start)) return rest;
  state.open = true;
  return rest.slice(0, start);
}

function ligatureNames(source: string): string[] {
  const found: string[] = [];
  const state = { open: false };
  source.split('\n').forEach((raw) => {
    const line = outsideComment(raw, state);
    for (const attr of ICON_ATTRS)
      for (const m of line.matchAll(
        new RegExp(`(?<![:\\w-])${attr}="([a-z0-9_]+)"`, 'g'),
      ))
        found.push(m[1]);
    // `<ModuleIcon name="…">` renders a custom module SVG, so only q-icon counts.
    for (const m of line.matchAll(
      /<q-icon\b[^>]*?(?<![:\w-])name="([a-z0-9_]+)"/g,
    ))
      found.push(m[1]);
    for (const m of line.matchAll(/\bicon:\s*['"]([a-z0-9_]+)['"]/g))
      found.push(m[1]);
    // ternary branches inside an already-bound expression
    for (const bound of line.matchAll(/:(?:name|icon[a-z-]*)="([^"]*)"/g))
      for (const m of bound[1].matchAll(/[?:]\s*'([a-z0-9_]+)'/g))
        found.push(m[1]);
  });
  return found;
}

test('no icon is referenced by webfont ligature name', () => {
  const offenders = sourceFiles(SRC).flatMap((file) =>
    ligatureNames(readFileSync(file, 'utf8')).map(
      (name) => `${path.relative(FRONTEND, file)}: ${name}`,
    ),
  );
  expect(offenders).toEqual([]);
});

test('quasar.config.js loads no icon webfont', () => {
  const config = readFileSync(path.join(FRONTEND, 'quasar.config.js'), 'utf8');
  expect(config).toContain('extras: []');
  expect(config).toContain("iconSet: 'svg-material-icons'");
});

test('a converted component renders an inline SVG, not a font glyph', async ({
  mount,
}) => {
  const component = await mount(ChartContainer, { props: { title: 'CO2' } });
  await expect(component.locator('svg path').first()).toBeAttached();
  await expect(component.locator('.material-icons')).toHaveCount(0);
});

test('the icon set Storybook and the CT harness install is the SVG one', () => {
  // Both harnesses pass this object to `app.use(Quasar, { iconSet })`. A bad
  // default-export interop would hand Quasar a module namespace instead, and
  // its internal icons would silently fall back to ligature names.
  expect(svgMaterialIcons.name).toBe('svg-material-icons');
  // Path data, not a ligature word — Quasar's own arrows/carets render as SVG.
  expect(svgMaterialIcons.arrow.dropdown).toMatch(/^M[\d.\s]/);
});
