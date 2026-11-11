/**
 * Operations links of the system logs page come from APP_SYSTEM_LINKS (#500).
 */
import { test, expect } from 'playwright/test';

import { parseSystemLinks } from '../../src/config/systemLinks';

const ONE_ENV = JSON.stringify([
  {
    name: 'dev',
    gitops: [{ label: 'GitOps', url: 'https://gitops.example' }],
    monitoring: [],
    appLogs: [],
    platform: [],
  },
]);

test('an empty value means no links', () => {
  expect(parseSystemLinks('')).toEqual([]);
});

test('a JSON array of environments parses', () => {
  expect(parseSystemLinks(ONE_ENV)[0].gitops[0].url).toBe(
    'https://gitops.example',
  );
});

test('an environment without its link groups is refused', () => {
  expect(() => parseSystemLinks('[{"name":"dev"}]')).toThrow(
    'APP_SYSTEM_LINKS must be a JSON array',
  );
});

test('a value that is not JSON is refused', () => {
  expect(() => parseSystemLinks('not json')).toThrow();
});
