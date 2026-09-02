export interface Co2FirstLoad {
  /** Milligrams of CO₂-eq for a first, uncached load of the app. */
  mg: number;
  /** Gzipped first-load transfer in KB. */
  kb: number;
}

/**
 * Reads the first-load CO₂ figure baked into index.html at build time by
 * scripts/inject-co2.mjs. Returns null when the meta tag is absent (dev
 * server), in which case the badge is simply not rendered.
 */
export function useCo2FirstLoad(): Co2FirstLoad | null {
  const content = document
    .querySelector('meta[name="co2-first-load"]')
    ?.getAttribute('content');
  if (!content) return null;

  const [mg, kb] = content.split('|').map(Number);
  if (!Number.isFinite(mg) || !Number.isFinite(kb)) return null;

  return { mg: Math.round(mg), kb: Math.round(kb) };
}
