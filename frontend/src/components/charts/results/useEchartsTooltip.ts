import { ref, computed, onBeforeUnmount } from 'vue';
import type { TooltipState } from 'src/types/chartTooltip';
import type { EChartsType } from 'echarts/types/dist/shared';

type InternalTooltipState = {
  visible: boolean;
  x: number;
  y: number;
  data: TooltipState;
};

type ZrMouseEvent = {
  offsetX: number;
  offsetY: number;
};

type ZrOnHandler = ((e: ZrMouseEvent) => void) | (() => void);

type ZrLike = {
  on: (event: string, handler: ZrOnHandler) => void;
};

type UpdateAxisPointerParams = {
  axesInfo?: Array<Record<string, unknown>>;
};

export function useEchartsTooltip() {
  const tooltip = ref<InternalTooltipState>({
    visible: false,
    x: 0,
    y: 0,
    data: null,
  });

  const cleanupFns: Array<() => void> = [];
  const lastMouse = { x: 0, y: 0 };

  function emitTooltip(state: TooltipState) {
    if (state === null) {
      tooltip.value.visible = false;
      tooltip.value.data = null;
      return;
    }
    tooltip.value = {
      visible: true,
      x: lastMouse.x,
      y: lastMouse.y,
      data: state,
    };
  }

  function attach(chart: EChartsType) {
    const zr = chart.getZr() as ZrLike;
    const canvas: HTMLElement = chart.getDom();

    zr.on('mousemove', (e: ZrMouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      lastMouse.x = rect.left + e.offsetX;
      lastMouse.y = rect.top + e.offsetY;
    });

    chart.on('updateAxisPointer', (params: UpdateAxisPointerParams) => {
      const axis = params.axesInfo?.[0];
      if (!axis) {
        tooltip.value.visible = false;
        return;
      }
      tooltip.value.visible = true;
      tooltip.value.x = lastMouse.x;
      tooltip.value.y = lastMouse.y;
    });

    // Hide when mouse leaves a data item (needed for trigger:'item' charts)
    chart.on('mouseout', () => {
      tooltip.value.visible = false;
    });

    zr.on('globalout', () => {
      tooltip.value.visible = false;
    });
  }

  onBeforeUnmount(() => {
    cleanupFns.forEach((fn) => fn());
  });

  const style = computed(() => {
    const offset = 12;

    let x = tooltip.value.x + offset;
    let y = tooltip.value.y + offset;

    const maxW = 280;
    const maxH = 160;

    if (x + maxW > window.innerWidth) {
      x = tooltip.value.x - maxW;
    }

    if (y + maxH > window.innerHeight) {
      y = tooltip.value.y - maxH;
    }

    return {
      position: 'fixed',
      left: `${x}px`,
      top: `${y}px`,
      pointerEvents: 'none',
      zIndex: 9999,
    };
  });

  return {
    tooltip,
    style,
    attach,
    emitTooltip,
  };
}
