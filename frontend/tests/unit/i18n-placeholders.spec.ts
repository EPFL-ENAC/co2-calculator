/**
 * #3244 — the texts name the institution through %placeholder% tokens that
 * src/i18n/index.ts fills at startup. A value must reach vue-i18n as literal
 * text, and a typo in a token must fail loudly instead of showing %token%.
 */

import { test, expect } from 'playwright/test';

import { fillPlaceholders } from '../../src/utils/i18nPlaceholders';

const values = {
  institution: 'UNIV',
  institution_fr_de: "de l'UNIV",
  contact_email: 'help@example.org',
};

test('placeholders are replaced by their values', () => {
  expect(fillPlaceholders('Strategy %institution_fr_de%', values, 'k')).toBe(
    "Strategy de l'UNIV",
  );
  expect(fillPlaceholders('%institution%: %institution%', values, 'k')).toBe(
    'UNIV: UNIV',
  );
});

test('vue-i18n syntax characters in a value are escaped', () => {
  expect(fillPlaceholders('mailto:%contact_email%', values, 'k')).toBe(
    "mailto:help{'@'}example.org",
  );
  expect(
    fillPlaceholders('%institution%', { institution: 'A|B {x} $y' }, 'k'),
  ).toBe("A{'|'}B {'{'}x{'}'} {'$'}y");
});

test('an unknown placeholder throws with the key and the token', () => {
  expect(() => fillPlaceholders('%instituton%', values, 'home_title')).toThrow(
    'i18n key "home_title" uses unknown placeholder %instituton%',
  );
});

test('a percent sign that is not a token stays', () => {
  expect(fillPlaceholders('50% of %institution%', values, 'k')).toBe(
    '50% of UNIV',
  );
});
