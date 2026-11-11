/**
 * Institution theme (#500): theme.env sets the --theme-* properties that the
 * SCSS tokens read.
 */
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { test, expect } from 'playwright/test';

import { THEME_TOKENS, parseThemeEnv } from '../../src/utils/institutionTheme';

const FRONTEND_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);

test('the token list and the stylesheet name the same theme tokens', () => {
  const options = readFileSync(
    path.join(FRONTEND_DIR, 'src/css/02-tokens/_options.scss'),
    'utf8',
  );
  const declared = [
    ...options.matchAll(/\$tokens-[a-z0-9-]+:\s*var\(\s*--theme-([a-z0-9-]+)/g),
  ].map((match) => match[1]);
  expect(declared.sort()).toEqual([...THEME_TOKENS].sort());
});

test('the EPFL theme parses', () => {
  const text = readFileSync(
    path.join(FRONTEND_DIR, 'institution/epfl/theme.env'),
    'utf8',
  );
  expect(parseThemeEnv(text)['colors-accent']).toBe('#ff0000');
});

test('comments and blank lines are skipped, values are trimmed', () => {
  expect(
    parseThemeEnv(
      '# theme\n\ncolors-accent = #003366 \ncolors-leman=#00a79f\n',
    ),
  ).toEqual({ 'colors-accent': '#003366', 'colors-leman': '#00a79f' });
});

test('an unknown token stops the startup with its line', () => {
  expect(() =>
    parseThemeEnv('colors-accent=#003366\ncolors-acent-hover=#000000'),
  ).toThrow('line 2: unknown token "colors-acent-hover"');
});

test('a theme without the accent stops the startup', () => {
  expect(() => parseThemeEnv('colors-leman=#00a79f')).toThrow(
    'theme.env must set colors-accent',
  );
});

test('a line without a value stops the startup', () => {
  expect(() => parseThemeEnv('colors-accent=')).toThrow('expected token=value');
});

// A theme token is a CSS variable: Sass rgba(), lighten() and the like produce
// invalid CSS on it, and the browser silently drops the whole declaration.
// That is how the login overlay lost its fade. This scan lists the tokens
// that alias a theme token and refuses a Sass color function on them.
test('no Sass color function is applied to a theme token', () => {
  const tokensDir = path.join(FRONTEND_DIR, 'src/css/02-tokens');
  const alias = new Map<string, string>();
  const themed = new Set<string>();
  for (const file of readdirSync(tokensDir)) {
    const text = readFileSync(path.join(tokensDir, file), 'utf8');
    for (const m of text.matchAll(
      /\$(tokens-[a-z0-9-]+):\s*var\(\s*--theme/g,
    )) {
      themed.add(m[1]);
    }
    for (const m of text.matchAll(
      /\$([a-z0-9-]+):\s*(?:opt|dec|cmp)\.\$([a-z0-9-]+)/g,
    )) {
      alias.set(m[1], m[2]);
    }
  }
  const isThemed = (name: string): boolean => {
    let current = name;
    for (let depth = 0; depth < 5 && alias.has(current); depth += 1) {
      current = alias.get(current) as string;
    }
    return themed.has(current);
  };
  const offenders: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(scss|vue)$/.test(entry.name)) {
        const text = readFileSync(full, 'utf8');
        for (const m of text.matchAll(
          /\b(rgba|lighten|darken|transparentize|mix)\(\s*[a-z.]*\$([a-z0-9-]+)/g,
        )) {
          if (isThemed(m[2])) offenders.push(`${full}: ${m[1]}($${m[2]})`);
        }
      }
    }
  };
  walk(path.join(FRONTEND_DIR, 'src'));
  expect(offenders).toEqual([]);
});
