/**
 * #2613 — planner headcount category labels come from the backend.
 *
 * `i18n/headcount_factor.ts` is gone: the grid fetches the
 * planner_headcount taxonomy vocabulary (seeded sius labels, request
 * locale) and labels every row from it — rows without an entry included.
 * The students row is a UI construct and keeps its own i18n key.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import PlannerHeadcountRows from '@/components/organisms/planner/PlannerHeadcountRows.vue';

test('rows are labelled from the taxonomy vocabulary', async ({
  mount,
  page,
}) => {
  await page.route('**/api/v1/carbon-reports/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{ id: 1, sius_code: '51', fte: 2 }],
      }),
    }),
  );
  await page.route(
    '**/api/v1/taxonomies/module/headcount/planner_headcount*',
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          name: 'planner_headcount',
          label: 'planner_headcount',
          children: [
            { name: '51', label: 'Professors' },
            { name: '52', label: 'Other teaching staff' },
          ],
        }),
      }),
  );

  const component = await mount(PlannerHeadcountRows, {
    props: { carbonReportId: 7, year: '2026', disable: false },
  });

  // A row backed by an entry and an empty row both resolve through the
  // vocabulary; a code outside the mocked vocabulary keeps the bare code.
  await expect(component.locator('label[for="fte-51"]')).toHaveText(
    'Professors',
  );
  await expect(component.locator('label[for="fte-52"]')).toHaveText(
    'Other teaching staff',
  );
  await expect(component.locator('label[for="fte-53"]')).toHaveText('53');
});
