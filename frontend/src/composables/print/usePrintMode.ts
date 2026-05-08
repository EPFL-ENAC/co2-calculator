import { computed, inject, provide, type ComputedRef } from 'vue';

const PRINT_MODE_KEY: unique symbol = Symbol('printMode');

export function providePrintMode(enabled: boolean): void {
  provide(PRINT_MODE_KEY, enabled);
}

export function usePrintMode(): ComputedRef<boolean> {
  const injected = inject<boolean | null>(PRINT_MODE_KEY, null);
  return computed(() => injected === true);
}
