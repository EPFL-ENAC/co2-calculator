/**
 * #1186: a traveler can type a station/airport name into the direction
 * inputs without picking an autocomplete suggestion. The free-text value
 * (`form.origin`/`form.destination`) then looks non-empty, but the
 * identifier the backend resolves distance/emissions from — `origin_iata`
 * for plane, `origin_natural_key` for train — never gets set. The entry
 * would otherwise persist with zero emissions and only a backend log line
 * to notice it.
 */
export function isTravelLocationResolved(
  travelMode: 'plane' | 'train',
  iata: unknown,
  naturalKey: unknown,
): boolean {
  return travelMode === 'plane' ? Boolean(iata) : Boolean(naturalKey);
}
