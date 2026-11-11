/**
 * Institution tokens (#500).
 *
 * Translation files name the institution with %token% placeholders. These
 * tests cover the replacement helpers and scan `src/i18n` so a hardcoded
 * institution name does not come back.
 */

import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { test, expect } from 'playwright/test';

import {
  escapeForMessage,
  replaceInstitutionTokens,
} from '../../src/utils/institutionTokens';

const I18N_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../src/i18n',
);

test('a token is replaced by the configured value', () => {
  expect(
    replaceInstitutionTokens('Emissions %institution_fr_de% in %institution%', {
      institution: 'CERN',
      institution_fr_de: 'du CERN',
    }),
  ).toBe('Emissions du CERN in CERN');
});

test('an unknown token fails at load', () => {
  expect(() =>
    replaceInstitutionTokens('at %instituton%', { institution: 'CERN' }),
  ).toThrow('%instituton%');
});

test('a value is escaped for the vue-i18n message syntax', () => {
  expect(escapeForMessage('help@example.org')).toBe("help{'@'}example.org");
  expect(
    replaceInstitutionTokens('mailto:%contact_email%', {
      contact_email: 'help@example.org',
    }),
  ).toBe("mailto:help{'@'}example.org");
});

test('a percent sign in a normal sentence is not a token', () => {
  expect(replaceInstitutionTokens('from 50% to 60% of the total', {})).toBe(
    'from 50% to 60% of the total',
  );
});

test('no translation file hardcodes the institution name', () => {
  const violations: string[] = [];
  for (const file of readdirSync(I18N_DIR)) {
    if (!file.endsWith('.ts') || file === 'index.ts') continue;
    readFileSync(path.join(I18N_DIR, file), 'utf8')
      .split('\n')
      .forEach((text, index) => {
        if (/\bEPFL\b|\bSCIPER/.test(text)) {
          violations.push(`${file}:${index + 1} ${text.trim()}`);
        }
      });
  }
  expect(violations).toEqual([]);
});
