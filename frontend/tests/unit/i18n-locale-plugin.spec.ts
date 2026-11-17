/**
 * build/i18n-locale.mjs keeps one language of each { en, fr } text, so a
 * visitor downloads one language. A text it cannot split must stop the
 * build: a pair left as is would reach vue-i18n as an object.
 */
import { test, expect } from 'playwright/test';
import { parseAst } from 'vite';
import { keepLanguage } from '../../build/i18n-locale.mjs';

const SOURCE = `import { MODULES } from './modules';
export default {
  plain: { en: 'Hello', fr: 'Bonjour' },
  [MODULES.Headcount]: { fr: 'Effectif', en: 'Headcount' },
  built: { en: ({ named }) => named('a'), fr: ({ named }) => named('b') },
};
`;

const keep = (source: string, lang: string) =>
  keepLanguage(source, parseAst(source), lang, 'texts.ts');

test('keeps the chosen language of every text', () => {
  const french = keep(SOURCE, 'fr');
  expect(french).toContain("plain: 'Bonjour',");
  expect(french).toContain("[MODULES.Headcount]: 'Effectif',");
  expect(french).toContain("built: ({ named }) => named('b'),");
  expect(french).not.toContain('Hello');
  expect(keep(SOURCE, 'en')).toContain("[MODULES.Headcount]: 'Headcount',");
});

test('a text without both languages stops the build', () => {
  expect(() => keep("export default { only: { en: 'Hello' } };", 'en')).toThrow(
    /not an \{ en, fr \} pair/,
  );
  expect(() => keep("export default { bare: 'Hello' };", 'en')).toThrow(
    /not an \{ en, fr \} pair/,
  );
});
