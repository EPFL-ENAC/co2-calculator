import { test, expect } from '@playwright/test';

import type { ModuleField } from '../../src/constant/moduleConfig';
import {
  buildPrintColumns,
  renderPrintCell,
  type PrintCellContext,
  type PrintColumn,
} from '../../src/utils/printTable';

const translations: Record<string, string> = {
  'field.name': 'Name',
  'field.power': 'Power ({unit})',
  'option.laptop': 'Laptop',
  'process-emissions.category.fuel': 'Fuel',
};

const t = (key: string, params?: Record<string, unknown>) => {
  const raw = translations[key] ?? '';
  return raw.replace('{unit}', String(params?.unit ?? ''));
};
const te = (key: string) => key in translations;

function makeContext(overrides?: Partial<PrintCellContext>): PrintCellContext {
  return {
    t,
    te,
    taxonomyKindLabels: {},
    headcountMembers: new Map(),
    formatNumber: (value, options) =>
      new Intl.NumberFormat('de-CH', options).format(value),
    ...overrides,
  };
}

function makeColumn(overrides?: Partial<PrintColumn>): PrintColumn {
  return {
    name: 'name',
    label: 'Name',
    field: 'name',
    align: 'left',
    ...overrides,
  };
}

test('buildPrintColumns filters hidden fields and translates labels', () => {
  const fields: ModuleField[] = [
    { id: 'name', type: 'text', labelKey: 'field.name' },
    { id: 'power', type: 'number', labelKey: 'field.power', unit: 'W' },
    { id: 'hidden', type: 'text', hideIn: { table: true } },
  ];

  const columns = buildPrintColumns(fields, t);

  expect(columns.map((c) => c.name)).toEqual(['name', 'power']);
  expect(columns[0]?.label).toBe('Name');
  expect(columns[1]?.label).toBe('Power (W)');
});

test('buildPrintColumns fans out array labelKey into one column per entry', () => {
  const fields: ModuleField[] = [
    {
      id: 'usage',
      type: 'number',
      labelKey: ['field.name', 'field.power'],
      unit: 'h',
    },
  ];

  const columns = buildPrintColumns(fields, t);

  expect(columns.map((c) => c.name)).toEqual(['usage_0', 'usage_1']);
  expect(columns.every((c) => c.field === 'usage')).toBe(true);
  expect(columns[1]?.label).toBe('Power (h)');
});

test('renderPrintCell returns a dash for empty values', () => {
  const ctx = makeContext();
  const col = makeColumn();

  expect(renderPrintCell({}, col, ctx)).toBe('-');
  expect(renderPrintCell({ name: null }, col, ctx)).toBe('-');
  expect(renderPrintCell({ name: '' }, col, ctx)).toBe('-');
});

test('renderPrintCell formats kg_co2eq as integer', () => {
  const ctx = makeContext();
  const col = makeColumn({ name: 'kg_co2eq', field: 'kg_co2eq' });

  expect(renderPrintCell({ kg_co2eq: 1234.56 }, col, ctx)).toBe("1'235");
});

test('renderPrintCell translates option labels', () => {
  const ctx = makeContext();
  const col = makeColumn({
    options: [
      { value: 'laptop', label: 'option.laptop' },
      { value: 'screen', label: 'Screen' },
    ],
  });

  expect(renderPrintCell({ name: 'laptop' }, col, ctx)).toBe('Laptop');
  expect(renderPrintCell({ name: 'screen' }, col, ctx)).toBe('Screen');
});

test('renderPrintCell resolves optionLabelKey templates', () => {
  const ctx = makeContext();
  const col = makeColumn({
    optionLabelKey: 'process-emissions.category.{value}',
  });

  expect(renderPrintCell({ name: 'FUEL' }, col, ctx)).toBe('Fuel');
  expect(renderPrintCell({ name: 'unknown' }, col, ctx)).toBe('unknown');
});

test('renderPrintCell resolves kind values from the taxonomy map', () => {
  const ctx = makeContext({
    taxonomyKindLabels: { server: 'Server rack' },
  });
  const col = makeColumn({ optionsId: 'kind' });

  expect(renderPrintCell({ name: 'server' }, col, ctx)).toBe('Server rack');
  expect(renderPrintCell({ name: 'other' }, col, ctx)).toBe('other');
});

test('renderPrintCell appends IATA codes to origin and destination', () => {
  const ctx = makeContext();
  const col = makeColumn({ name: 'origin_name', field: 'origin_name' });

  expect(
    renderPrintCell({ origin_name: 'Geneva', origin_iata: 'GVA' }, col, ctx),
  ).toBe('Geneva (GVA)');
  expect(renderPrintCell({ origin_name: 'Geneva' }, col, ctx)).toBe('Geneva');
  expect(renderPrintCell({}, col, ctx)).toBe('-');
});

test('renderPrintCell resolves traveler names from headcount members', () => {
  const ctx = makeContext({
    headcountMembers: new Map([['123456', 'Ada Lovelace']]),
  });
  const col = makeColumn({ name: 'traveler_name', field: 'traveler_name' });

  expect(renderPrintCell({ user_institutional_id: '123456' }, col, ctx)).toBe(
    'Ada Lovelace',
  );
  expect(renderPrintCell({ user_institutional_id: '999999' }, col, ctx)).toBe(
    '-',
  );
  expect(renderPrintCell({}, col, ctx)).toBe('-');
});

test('renderPrintCell formats plain numbers with module format options', () => {
  const ctx = makeContext({
    numberFormatOptions: { maximumFractionDigits: 1 },
  });
  const col = makeColumn({ name: 'fte', field: 'fte' });

  expect(renderPrintCell({ fte: 2.25 }, col, ctx)).toBe('2.3');
});
