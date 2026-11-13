import { test, expect } from '@playwright/experimental-ct-vue';
import EquipmentPowerFeedbackDialog from '../../src/components/molecules/EquipmentPowerFeedbackDialog.vue';

/**
 * #3244 — APP_EQUIPMENT_POWER_FEEDBACK_EMAIL is empty unless the deployment
 * sets it. The test institution does not set it. Without a recipient, the
 * request tab must not offer a mailto that opens a draft with no address.
 */
test('without a recipient, the dialog has no power request tab', async ({
  mount,
  page,
}) => {
  await mount(EquipmentPowerFeedbackDialog, {
    props: {
      modelValue: true,
      equipmentName: 'Freezer',
      equipmentClass: 'Cold',
      unitName: 'Unit',
      year: 2024,
    },
  });
  const tabs = page.locator('.q-dialog .q-tab');
  await expect(tabs).toHaveCount(1);
  await expect(page.locator('.q-dialog a[href^="mailto:"]')).toHaveCount(0);
});
