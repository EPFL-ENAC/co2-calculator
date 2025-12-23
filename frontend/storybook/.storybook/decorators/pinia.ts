import { createPinia, setActivePinia, type Pinia } from 'pinia';
import type { Decorator } from '@storybook/vue3';

/**
 * Decorator that provides a fresh Pinia instance for each story.
 * Prevents state leakage between stories.
 */
export const withPinia: Decorator = (story) => {
  const pinia = createPinia();
  setActivePinia(pinia);

  return {
    components: { story },
    setup() {
      return { pinia };
    },
    template: '<story />',
  };
};

/**
 * Helper to create a Pinia decorator with mock store state.
 * Useful for stories that need specific store configurations.
 *
 * @param setupStores - Function that receives the Pinia instance and sets up store state
 *
 * @example
 * ```ts
 * export const WithTimeline = {
 *   decorators: [
 *     withMockStore((pinia) => {
 *       const timelineStore = useTimelineStore(pinia);
 *       timelineStore.$patch(mockTimelineState);
 *     })
 *   ],
 * };
 * ```
 */
export const withMockStore = (
  setupStores: (pinia: Pinia) => void,
): Decorator => {
  return (story) => {
    const pinia = createPinia();
    setActivePinia(pinia);

    // Setup stores with mock data
    setupStores(pinia);

    return {
      components: { story },
      setup() {
        return { pinia };
      },
      template: '<story />',
    };
  };
};
