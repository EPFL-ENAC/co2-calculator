/**
 * Regression test for the y-axis name overlapping its tick labels — in the
 * main Results bar chart, a fixed ``nameGap: 40`` put "t CO₂-eq" on top of
 * labels like ``180,000,000,000`` once totals reached the billions, and the
 * first attempt at a wider gap pushed the name off the canvas instead.
 *
 * ECharts 6 resolves both itself (``nameMoveOverlap`` keeps the name clear
 * of the labels, ``grid.outerBounds`` keeps it on the canvas) as long as the
 * chart does not pass the legacy ``grid.containLabel``. This mounts the real
 * chart with a 165-billion-tonne bar and checks where the name landed.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import AxisNameOverlapHarness from './AxisNameOverlapHarness.vue';
import type { AxisNameLayout } from './AxisNameOverlapHarness.vue';

type Rect = AxisNameLayout['name'];

function overlaps(a: Rect, b: Rect): boolean {
  return (
    a.x < b.x + b.width &&
    b.x < a.x + a.width &&
    a.y < b.y + b.height &&
    b.y < a.y + a.height
  );
}

test('y-axis name stays on canvas and clear of billion-scale tick labels', async ({
  mount,
}) => {
  const component = await mount(AxisNameOverlapHarness);
  const report = component.getByTestId('axis-name-layout');
  await expect(report).not.toBeEmpty({ timeout: 8000 });

  const layout = JSON.parse(
    (await report.textContent()) ?? '',
  ) as AxisNameLayout;

  // The widest label really is billion-scale, i.e. the bug's input.
  const widest = Math.max(...layout.labels.map((l) => l.width));
  expect(widest).toBeGreaterThan(60);

  // Fully inside the canvas: not clipped on the left like the first fix.
  expect(layout.name.x).toBeGreaterThanOrEqual(0);
  expect(layout.name.x + layout.name.width).toBeLessThanOrEqual(
    layout.canvasWidth,
  );

  // Left of every label, with no intersection at all.
  for (const label of layout.labels) {
    expect(overlaps(layout.name, label)).toBe(false);
    expect(layout.name.x + layout.name.width).toBeLessThanOrEqual(label.x);
  }
});
