import { test, expect } from '@playwright/experimental-ct-vue';
import App from '../src/App.vue';

test('should work', async ({ mount }) => {
  const component = await mount(App);
  await expect(component).toContainText('');
});
