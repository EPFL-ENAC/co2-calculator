import { CURRENCY_CODES } from '@/types/module-lookups.gen';

/**
 * The currencies the app accepts for money amounts, shared by the Purchase
 * module fields and the planner's grant budget (#1978). Values are the
 * lowercase codes the backend stores (generated from SUPPORTED_CURRENCIES);
 * labels are the display codes.
 */
export const CURRENCY_OPTIONS: { value: string; label: string }[] =
  CURRENCY_CODES.map((value) => ({ value, label: currencyLabel(value) }));

/** Display code of a stored currency value ('chf' -> 'CHF'); '' when unset. */
export function currencyLabel(value: string | null | undefined): string {
  return value ? value.toUpperCase() : '';
}
