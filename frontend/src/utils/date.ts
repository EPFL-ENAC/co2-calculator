/**
 * Format a date as a relative time string using Intl.RelativeTimeFormat
 * @param dateString - ISO date string
 * @param locale - Locale string (e.g., 'en-US', 'fr-CH')
 * @param prefix - Optional prefix to add (e.g., 'Active')
 * @returns Formatted relative time string
 */
export function formatRelativeTime(
  dateString: string,
  locale: string,
  prefix = 'Active',
): string {
  const date = parseUtcDate(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });

  const intervals = [
    { seconds: 31536000, unit: 'year' as const },
    { seconds: 2592000, unit: 'month' as const },
    { seconds: 86400, unit: 'day' as const },
    { seconds: 3600, unit: 'hour' as const },
    { seconds: 60, unit: 'minute' as const },
  ];

  for (const interval of intervals) {
    const count = Math.floor(diffInSeconds / interval.seconds);
    if (count >= 1) {
      return `${prefix} ${rtf.format(-count, interval.unit)}`;
    }
  }

  // Less than a minute ago
  return `${prefix} ${rtf.format(0, 'minute')}`;
}

export function parseUtcDate(dateString: string): Date {
  if (!dateString) {
    return new Date(NaN);
  }

  if (
    dateString.endsWith('Z') ||
    dateString.includes('+') ||
    dateString.includes('-')
  ) {
    return new Date(dateString);
  }

  const isoMatch = dateString.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$/,
  );
  if (isoMatch) {
    const [, year, month, day, hour, minute, second, ms] = isoMatch;
    return new Date(
      Date.UTC(
        parseInt(year, 10),
        parseInt(month, 10) - 1,
        parseInt(day, 10),
        parseInt(hour, 10),
        parseInt(minute, 10),
        parseInt(second, 10),
        ms ? parseInt(ms.padEnd(3, '0').slice(0, 3), 10) : 0,
      ),
    );
  }

  return new Date(dateString);
}
