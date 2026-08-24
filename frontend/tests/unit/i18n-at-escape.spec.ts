/**
 * Regression test for the vue-i18n "@" escape in translation files.
 *
 * vue-i18n treats a raw "@" inside a message as linked-message syntax: it
 * compiles in dev but throws a SyntaxError at render time in production
 * builds. Smart-quoted placeholders such as {‘@’} (introduced by editing
 * translations through a word processor) fail message compilation outright
 * ("Invalid token in placeholder"). The only safe form is the literal escape
 * {'@'} with straight quotes.
 *
 * This scans every file in ``src/i18n`` and asserts each "@" character is
 * part of the exact sequence {'@'}.
 */

import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { test, expect } from '@playwright/test';

const I18N_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../src/i18n',
);
const ESCAPED_AT = "{'@'}";

function findUnescapedAt(source: string): { line: number; context: string }[] {
  const violations: { line: number; context: string }[] = [];
  source.split('\n').forEach((text, index) => {
    for (
      let col = text.indexOf('@');
      col !== -1;
      col = text.indexOf('@', col + 1)
    ) {
      if (text.slice(col - 2, col + 3) !== ESCAPED_AT) {
        violations.push({ line: index + 1, context: text.trim() });
      }
    }
  });
  return violations;
}

test('findUnescapedAt flags the known breakages and accepts the escape', () => {
  expect(findUnescapedAt("en: 'contact co2calculator@epfl.ch'")).toHaveLength(
    1,
  );
  expect(
    findUnescapedAt("en: 'contact co2calculator{‘@’}epfl.ch'"),
  ).toHaveLength(1);
  expect(
    findUnescapedAt('en: "contact co2calculator{\'@\'}epfl.ch"'),
  ).toHaveLength(0);
});

test("every @ in src/i18n is escaped as {'@'}", () => {
  const files = readdirSync(I18N_DIR).filter((file) => file.endsWith('.ts'));
  expect(files.length).toBeGreaterThan(0);

  const failures = files.flatMap((file) =>
    findUnescapedAt(readFileSync(path.join(I18N_DIR, file), 'utf8')).map(
      ({ line, context }) => `${file}:${line} — ${context}`,
    ),
  );

  expect(failures, `unescaped @ in translations, use {'@'}`).toEqual([]);
});
