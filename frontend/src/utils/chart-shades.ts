export const STACK_SHADE_ORDER = [
  'darker',
  'dark',
  'default',
  'light',
  'lighter',
] as const;

export type StackShadeName = (typeof STACK_SHADE_ORDER)[number];

export type ShadeScale = Record<StackShadeName, string>;

/**
 * Shade for the i-th segment counted from the bottom of a stacked bar:
 * index 0 (bottom) is darkest, lightening upward. Index clamps to [0, 4].
 */
export function stackShade(scale: ShadeScale, index: number): string {
  const clamped = Math.min(Math.max(index, 0), STACK_SHADE_ORDER.length - 1);
  return scale[STACK_SHADE_ORDER[clamped]];
}
