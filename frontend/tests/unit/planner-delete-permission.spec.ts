/**
 * Unit tests for `canDeletePlan` — the helper gating the planner table's
 * delete button (`CO2ProjectPlanner.vue`).
 *
 * Plan 2043 listed this file but it was never committed, which is how the
 * over-permitting unit-breadth branch survived unnoticed (#2607). The helper
 * mirrors the backend `PlanPolicy.can_delete`: `global` breadth deletes any
 * plan, every other breadth is creator-only. The button is UX only — the
 * backend DELETE stays the authority.
 */

import { test, expect } from '@playwright/test';

import { canDeletePlan } from '../../src/utils/permission';

const CF = '0184';
const ME = 7;
const SOMEONE_ELSE = 9;

test('global breadth deletes any plan, including a colleague’s', () => {
  const perms = { 'planner.plans': ['view', 'edit', 'delete'] } as never;
  expect(canDeletePlan(perms, CF, ME, SOMEONE_ELSE)).toBe(true);
  expect(canDeletePlan(perms, CF, ME, ME)).toBe(true);
});

test('own breadth deletes the plans the user created', () => {
  const perms = {
    'planner.plans/0184/own': ['view', 'edit', 'delete'],
  } as never;
  expect(canDeletePlan(perms, CF, ME, ME)).toBe(true);
});

test('own breadth does not delete a colleague’s shared plan', () => {
  const perms = {
    'planner.plans/0184/own': ['view', 'edit', 'delete'],
  } as never;
  expect(canDeletePlan(perms, CF, ME, SOMEONE_ELSE)).toBe(false);
});

test('principal keys delete own plans only', () => {
  // What CO2_USER_PRINCIPAL actually holds: unit-breadth view/edit, own-breadth
  // delete. Deleting a colleague's plan stays creator-only by design (#1930).
  const perms = {
    'planner.plans/0184': ['view', 'edit'],
    'planner.plans/0184/own': ['delete'],
  } as never;
  expect(canDeletePlan(perms, CF, ME, ME)).toBe(true);
  expect(canDeletePlan(perms, CF, ME, SOMEONE_ELSE)).toBe(false);
});

test('unit-breadth delete stays creator-only, as the backend enforces', () => {
  // Regression for #2607: the helper used to return true for any plan here,
  // while `PlanPolicy.can_delete` short-circuits on `global` only and otherwise
  // falls back to `created_by == user_id` — an enabled button plus a 403.
  const perms = {
    'planner.plans/0184': ['view', 'edit', 'delete'],
  } as never;
  expect(canDeletePlan(perms, CF, ME, ME)).toBe(true);
  expect(canDeletePlan(perms, CF, ME, SOMEONE_ELSE)).toBe(false);
});

test('no planner key denies deletion', () => {
  expect(canDeletePlan({} as never, CF, ME, ME)).toBe(false);
  expect(canDeletePlan(null, CF, ME, ME)).toBe(false);
});

test('no unit context denies deletion below global breadth', () => {
  const perms = {
    'planner.plans/0184/own': ['view', 'edit', 'delete'],
  } as never;
  expect(canDeletePlan(perms, null, ME, ME)).toBe(false);
});

test('an unidentified user never deletes below global breadth', () => {
  const perms = {
    'planner.plans/0184/own': ['view', 'edit', 'delete'],
  } as never;
  expect(canDeletePlan(perms, CF, null, null)).toBe(false);
});
