/**
 * #3099 — ModuleSelector's checkbox handler takes the state key (a plain
 * closure over an imported constant tripped vue-tsc 3.3.13). The emitted
 * reporting filter must still carry MODULE_STATES values, not the keys.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import ModuleSelector from '@/components/organisms/backoffice/reporting/ModuleSelector.vue';
import { MODULE_STATES, type ModuleState } from '@/constant/moduleStates';

const PROPS = {
  moduleCard: { module: 'headcount' as const, active: true },
  modelValue: [MODULE_STATES.Default] as ModuleState[],
};

test('ticking a state adds its value, unticking removes it', async ({
  mount,
}) => {
  const emitted: ModuleState[][] = [];
  const component = await mount(ModuleSelector, {
    props: PROPS,
    on: {
      'update:modelValue': (states: ModuleState[]) => emitted.push(states),
    },
  });
  // Checkboxes follow MODULE_STATES order: Default, InProgress, Validated.
  const boxes = component.getByRole('checkbox');

  await boxes.nth(1).click();
  await expect
    .poll(() => emitted.at(-1))
    .toEqual([MODULE_STATES.Default, MODULE_STATES.InProgress]);

  await boxes.nth(0).click();
  await expect.poll(() => emitted.at(-1)).toEqual([]);
});
