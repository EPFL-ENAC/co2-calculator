/**
 * Regression test for the chart color-scale bug — in the main Results stacked
 * bar chart, some bars rendered a darker shade above a lighter one.
 *
 * ECharts stacks series sharing ``stack: 'total'`` in series-array order
 * (first series = bottom segment). ``stackShade`` (``utils/chart-shades.ts``)
 * pins the shade to the segment's position: index 0 (bottom) is darkest,
 * lightening upward. ``ModuleCarbonFootprintChart.vue`` uses it for the
 * value-ranked equipment/purchases stacks, so the largest subcategory is
 * always the darkest bottom segment regardless of which subcategory ranks
 * first. This test pins the darkest-bottom invariant and the index→shade
 * contract.
 */

import { test, expect } from '@playwright/test';

import {
  STACK_SHADE_ORDER,
  stackShade,
  type ShadeScale,
} from '../../src/utils/chart-shades';

// paleYellowGreen default-mode scale from ``constant/charts.ts``
const scale: ShadeScale = {
  darker: '#ABCF84',
  dark: '#C0DEA0',
  default: '#D5EBBE',
  light: '#E5F2D4',
  lighter: '#F0F8EA',
};

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

test('shades lighten monotonically from the bottom of the stack upward', () => {
  for (let i = 1; i < STACK_SHADE_ORDER.length; i++) {
    expect(luminance(stackShade(scale, i))).toBeGreaterThan(
      luminance(stackShade(scale, i - 1)),
    );
  }
});

test('index maps to the shade at the same position in STACK_SHADE_ORDER', () => {
  STACK_SHADE_ORDER.forEach((name, i) => {
    expect(stackShade(scale, i)).toBe(scale[name]);
  });
});

test('out-of-range indices clamp to the darkest and lightest shades', () => {
  expect(stackShade(scale, -1)).toBe(scale.darker);
  expect(stackShade(scale, STACK_SHADE_ORDER.length)).toBe(scale.lighter);
  expect(stackShade(scale, 99)).toBe(scale.lighter);
});
