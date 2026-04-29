import { ref, computed, onBeforeUnmount } from 'vue';

type TooltipState = {
  visible: boolean;
  x: number;
  y: number;
  data?: any;
};

export function useEchartsTooltip() {
  const tooltip = ref<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    data: undefined,
  });

  const cleanupFns: Array<() => void> = [];
  const lastMouse = { x: 0, y: 0 };

  function emitTooltip(params) {
    tooltip.value = {
      visible: true,
      x: lastMouse.x,
      y: lastMouse.y,
      data: params,
    };
  }

  function attach(chart: any) {
    const zr = chart.getZr();

    zr.on('mousemove', (e: any) => {
      lastMouse.x = e.offsetX;
      lastMouse.y = e.offsetY;
    });

    chart.on('updateAxisPointer', (params: any) => {
      const axis = params.axesInfo?.[0];

      if (!axis) {
        tooltip.value.visible = false;
        return;
      }

      tooltip.value.visible = true;
      tooltip.value.x = lastMouse.x;
      tooltip.value.y = lastMouse.y;
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
