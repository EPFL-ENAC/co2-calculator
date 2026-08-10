/**
 * The currencies the app accepts for money amounts, shared by the Purchase
 * module fields and the planner's grant budget (#1978). Values are the
 * lowercase codes the backend stores; labels are the display codes.
 */
export const CURRENCY_OPTIONS: { value: string; label: string }[] = [
  { value: 'aud', label: 'AUD' },
  { value: 'cad', label: 'CAD' },
  { value: 'chf', label: 'CHF' },
  { value: 'cny', label: 'CNY' },
  { value: 'eur', label: 'EUR' },
  { value: 'gbp', label: 'GBP' },
  { value: 'jpy', label: 'JPY' },
  { value: 'sek', label: 'SEK' },
  { value: 'usd', label: 'USD' },
];

/** Display code of a stored currency value ('chf' -> 'CHF'); '' when unset. */
export function currencyLabel(value: string | null | undefined): string {
  return value ? value.toUpperCase() : '';
}
