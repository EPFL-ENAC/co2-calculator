/** Bounds of the planner's "% of reference year" control. */
export const REFERENCE_PERCENTAGE_MIN = 0;
export const REFERENCE_PERCENTAGE_MAX = 100;

/**
 * Clamp a typed "% of reference year" into the slider's range.
 *
 * Returns ``null`` when the input is empty or not a number, so the caller can
 * leave the stored percentage alone instead of writing a guessed one.
 */
export function clampReferencePercentage(
  raw: string | number | null,
): number | null {
  if (raw === null || raw === '') return null;
  const value = typeof raw === 'number' ? raw : Number(raw);
  if (!Number.isFinite(value)) return null;
  return Math.min(
    REFERENCE_PERCENTAGE_MAX,
    Math.max(REFERENCE_PERCENTAGE_MIN, value),
  );
}
