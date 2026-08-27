/**
 * Unit test for the Equipment power-change-request mailto helpers (#266).
 *
 * ``buildPowerRequestBody`` produces the localized pre-filled textarea text
 * (equipment context filled in, suggested-value lines left blank).
 * ``buildMailtoUrl`` assembles the ``mailto:`` (recipient raw, subject/body
 * percent-encoded). Both are pure; the body builder takes an injected translator
 * so it can be tested for both locales without a live i18n runtime.
 */

import { test, expect } from '@playwright/test';

import {
  buildPowerRequestBody,
  buildMailtoUrl,
  type MailTranslate,
  type EquipmentPowerRequestData,
} from '../../src/utils/equipmentPowerFeedbackMail';

// Minimal fakes mirroring the real i18n templates in src/i18n/equipment.ts.
function makeTranslate(locale: 'en' | 'fr'): MailTranslate {
  const dict: Record<'en' | 'fr', Record<string, string>> = {
    en: {
      'equipment-power-feedback-request-template':
        'Unit: {unitName}\nYear: {year}\nEquipment: {equipmentName}\n' +
        'Class: {equipmentClass}\nSub-class: {subClass}\n' +
        'Current estimated active power (W): {currentActivePowerW}\n' +
        'Current estimated standby power (W): {currentStandbyPowerW}\n' +
        'Suggested active power (W):\nSuggested standby power (W):\n' +
        'Data source:',
    },
    fr: {
      'equipment-power-feedback-request-template':
        'Unité : {unitName}\nAnnée : {year}\nÉquipement : {equipmentName}\n' +
        'Classe : {equipmentClass}\nSous-classe : {subClass}\n' +
        'Puissance active estimée actuelle (W) : {currentActivePowerW}\n' +
        'Puissance active suggérée (W) :',
    },
  };
  return (key, named) => {
    let out = dict[locale][key] ?? key;
    if (named) {
      for (const [k, v] of Object.entries(named)) {
        out = out.replaceAll(`{${k}}`, String(v));
      }
    }
    return out;
  };
}

const RECIPIENT = 'admin@example.org';

const DATA: EquipmentPowerRequestData = {
  equipmentName: 'Centrifuge X',
  equipmentClass: 'centrifuge',
  subClass: 'benchtop',
  currentActivePowerW: 1300,
  currentStandbyPowerW: 130,
  unitName: 'Lab ABC',
  year: 2026,
};

test('prefilled body embeds equipment context and leaves suggested values blank (EN)', () => {
  const body = buildPowerRequestBody(DATA, makeTranslate('en'));
  expect(body).toContain('Lab ABC');
  expect(body).toContain('2026');
  expect(body).toContain('Centrifuge X');
  expect(body).toContain('centrifuge');
  expect(body).toContain('benchtop');
  expect(body).toContain('Current estimated active power (W): 1300');
  // Suggested-value lines have no value after the colon.
  expect(body).toContain('Suggested active power (W):\n');
});

test('prefilled body localises and missing values become em-dash (FR)', () => {
  const body = buildPowerRequestBody(
    { ...DATA, subClass: null },
    makeTranslate('fr'),
  );
  expect(body).toContain('Équipement : Centrifuge X');
  expect(body).toContain('Sous-classe : —');
});

test('buildMailtoUrl keeps recipient raw and encodes subject/body', () => {
  const url = buildMailtoUrl(
    RECIPIENT,
    'Equipment power change request — Centrifuge X',
    'line one\nline two with spaces',
  );
  expect(url.startsWith(`mailto:${RECIPIENT}?subject=`)).toBe(true);
  expect(url).toContain('&body=');
  // Spaces/newlines must be percent-encoded, not raw.
  expect(url).not.toContain(' ');
  expect(url).not.toContain('\n');

  const subject = decodeURIComponent(
    url.split('?subject=')[1].split('&body=')[0],
  );
  const body = decodeURIComponent(url.split('&body=')[1]);
  expect(subject).toBe('Equipment power change request — Centrifuge X');
  expect(body).toBe('line one\nline two with spaces');
});

test('end-to-end: prefilled body round-trips through the mailto', () => {
  const body = buildPowerRequestBody(DATA, makeTranslate('en'));
  const url = buildMailtoUrl(RECIPIENT, 'Subject', body);
  expect(decodeURIComponent(url.split('&body=')[1])).toBe(body);
});
