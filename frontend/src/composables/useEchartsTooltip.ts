import { createVNode, onBeforeUnmount, ref, render } from 'vue';

import ChartTooltip from 'src/components/charts/ChartTooltip.vue';
import type { TooltipState } from 'src/types/chartTooltip';

type UseEchartsTooltipOptions = {
  buildState: (params: unknown) => TooltipState;
};

const TOOLTIP_ROOT_CLASS = 'js-vue-echarts-tooltip-root';

let tokenCounter = 0;

function nextToken(): string {
  tokenCounter += 1;
  return `t${tokenCounter}`;
}

function findTooltipRootByToken(token: string): HTMLElement | null {
  return document.querySelector(
    `.${TOOLTIP_ROOT_CLASS}[data-tooltip-token="${token}"]`,
  );
}

export function createEchartsTooltipFormatter(
  buildState: (params: unknown) => TooltipState,
): (params: unknown) => string {
  let lastToken: string | null = null;

  return (params: unknown): string => {
    const next = buildState(params);
    if (!next) {
      lastToken = null;
      return '';
    }
    if (typeof document === 'undefined') return '';

    const token = nextToken();
    lastToken = token;

    queueMicrotask(() => {
      if (lastToken !== token) return;
      const root = findTooltipRootByToken(token);
      if (!root) return;
      render(createVNode(ChartTooltip, { tooltipState: next }), root);
    });

    return `<div class="${TOOLTIP_ROOT_CLASS}" data-tooltip-token="${token}"></div>`;
  };
}

export function useEchartsTooltip(options: UseEchartsTooltipOptions): {
  tooltipState: Readonly<{ value: TooltipState }>;
  formatter: (params: unknown) => string;
} {
  const tooltipState = ref<TooltipState>(null);
  let lastMountedEl: HTMLElement | null = null;
  let lastToken: string | null = null;

  const formatter = (params: unknown): string => {
    const next = options.buildState(params);
    tooltipState.value = next;
    if (!next) {
      if (lastMountedEl) render(null, lastMountedEl);
      lastMountedEl = null;
      lastToken = null;
      return '';
    }

    if (typeof document === 'undefined') return '';

    const token = nextToken();
    lastToken = token;

    queueMicrotask(() => {
      if (lastToken !== token) return;
      const root = findTooltipRootByToken(token);
      if (!root) return;
      lastMountedEl = root;
      render(createVNode(ChartTooltip, { tooltipState: next }), root);
    });

    return `<div class="${TOOLTIP_ROOT_CLASS}" data-tooltip-token="${token}"></div>`;
  };

  onBeforeUnmount(() => {
    if (lastMountedEl) render(null, lastMountedEl);
    lastMountedEl = null;
    lastToken = null;
  });

  return { tooltipState, formatter };
}

