/**
 * Formats a number using Swiss German locale (de-CH)
 * This ensures consistent number formatting throughout the app:
 * - Thousands separator: apostrophe (')
 * - Decimal separator: dot (.)
 *
 * Example: 10750.64 -> "10'750.64"
 *
 * @param value - The number to format
 * @param options - Optional Intl.NumberFormatOptions for customization
 *   - For integers: { minimumFractionDigits: 0, maximumFractionDigits: 0 }
 *   - For specific decimals: { minimumFractionDigits: 2, maximumFractionDigits: 2 }
 * @returns Formatted number string
 */
export function formatNumber(
  value: number | string | null | undefined,
  options?: Intl.NumberFormatOptions,
): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }

  const numValue = typeof value === 'string' ? Number(value) : value;

  if (!Number.isFinite(numValue)) {
    return '-';
  }

  return new Intl.NumberFormat('de-CH', options).format(numValue);
}
