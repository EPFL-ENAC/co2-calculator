/**
 * #2706 — the headcount "FTE by function" chart reads the module's persisted
 * stats (member_fte_by_sius_code + student_fte) instead of a per-request
 * aggregate. Pins the shape the chart is fed from that JSON.
 */

import { test, expect } from '@playwright/test';

import { headcountChartStats } from '../../src/utils/headcountChart';

test('member groups become bars keyed by SIUS code, students as the sentinel', () => {
  expect(
    headcountChartStats({
      total_fte: 11.97,
      student_fte: 4,
      member_fte_by_sius_code: { '51': 5, '57': 2.97 },
    }),
  ).toEqual({ '51': 5, '57': 2.97, student: 4 });
});

test('a member group with no FTE recorded (null) draws no bar', () => {
  expect(
    headcountChartStats({
      student_fte: 0,
      member_fte_by_sius_code: { '51': null, '52': 1 },
    }),
  ).toEqual({ '52': 1, student: 0 });
});

test('a module without persisted stats yields no bars', () => {
  expect(headcountChartStats(null)).toEqual({});
  expect(headcountChartStats({ total: 12 })).toEqual({});
});
